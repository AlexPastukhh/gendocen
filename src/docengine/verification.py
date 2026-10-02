"""Read-only P6 project verification/release-gate report.

Verification deliberately aggregates findings instead of failing fast.  It never
advances dependency state, semantic baselines, receipts, or materialized outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .builders import BuildEngine, BuilderError, BuilderRegistry
from .dependencies import DependencyError, DependencyRuntime
from .materialization import MaterializationError, MaterializationRuntime, RendererRegistry
from .project import ProjectRoots
from .refs import ResourceRef
from .resources import ResourceCatalog, ResourceError
from .semantic import SemanticDependencyRegistry, SemanticReviewRuntime, SemanticRuleError


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    code: str
    severity: str
    message: str
    target: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.target is not None:
            result["target"] = self.target
        if self.details is not None:
            result["details"] = self.details
        return result


class VerificationRuntime:
    """Aggregate read-only verification over already-loaded project components."""

    def __init__(
        self,
        roots: ProjectRoots,
        *,
        catalog: ResourceCatalog | None,
        builders: BuilderRegistry | None,
        semantic_registry: SemanticDependencyRegistry | None,
        renderers: RendererRegistry | None,
        component_errors: Iterable[VerificationFinding] = (),
    ) -> None:
        self.roots = roots
        self.catalog = catalog
        self.builders = builders or BuilderRegistry()
        self.semantic_registry = semantic_registry or SemanticDependencyRegistry()
        self.renderers = renderers
        self.component_errors = tuple(component_errors)

    @staticmethod
    def _finding(
        code: str,
        message: str,
        *,
        severity: str = "blocking",
        target: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> VerificationFinding:
        return VerificationFinding(code, severity, message, target, details)

    @staticmethod
    def _dedupe(findings: Iterable[VerificationFinding]) -> list[VerificationFinding]:
        seen: set[tuple[str, str | None, str]] = set()
        result: list[VerificationFinding] = []
        for finding in findings:
            key = (finding.code, finding.target, finding.message)
            if key in seen:
                continue
            seen.add(key)
            result.append(finding)
        return sorted(result, key=lambda f: (f.severity != "blocking", f.code, f.target or "", f.message))

    def run(self) -> dict[str, Any]:
        findings: list[VerificationFinding] = list(self.component_errors)
        sections: dict[str, Any] = {}

        # Dependency runtime construction itself is domain verification work.  A
        # malformed/symlinked runtime tree must therefore become a blocking finding,
        # not escape to the CLI's generic internal-error boundary.
        runtime: DependencyRuntime | None = None
        runtime_error: str | None = None
        try:
            runtime = DependencyRuntime(
                self.roots,
                self.catalog,
                self.builders,
                semantic_rule_revisions=self.semantic_registry.revisions_by_target(),
            )
        except (DependencyError, OSError) as exc:
            runtime_error = str(exc)
            findings.append(self._finding("dependency_runtime_unavailable", runtime_error))
            sections["dependency_runtime"] = {"ok": False, "error": runtime_error}
            sections["dependency_integrity"] = {
                "ok": False,
                "issues": [{"code": "dependency_runtime_unavailable", "message": runtime_error}],
                "receipt_count": 0,
            }
            sections["dependency_state"] = {"error": runtime_error}
        else:
            sections["dependency_runtime"] = {"ok": True}
            integrity = runtime.verify_integrity()
            sections["dependency_integrity"] = integrity
            for issue in integrity.get("issues", []):
                findings.append(self._finding(
                    str(issue.get("code", "dependency_integrity_failed")),
                    str(issue.get("message", "dependency integrity failure")),
                ))

            try:
                state = runtime.status()
                sections["dependency_state"] = state
                for target, entry in sorted(state.get("targets", {}).items()):
                    status = entry.get("status")
                    if status != "valid":
                        findings.append(self._finding(
                            "unresolved_dependency_state",
                            f"target is {status}",
                            target=target,
                            details={"status": status, "reason_codes": entry.get("reason_codes", [])},
                        ))
            except DependencyError as exc:
                sections["dependency_state"] = {"error": str(exc)}
                findings.append(self._finding("dependency_state_unreadable", str(exc)))

        # Compare active receipts with current inputs without mutating state.
        current_checks: list[dict[str, Any]] = []
        if self.catalog is not None and runtime is not None:
            try:
                active = runtime.active_receipts()
                for target, receipt in sorted(active.items()):
                    try:
                        if self.semantic_registry.has_target(target):
                            packet = SemanticReviewRuntime(runtime, self.semantic_registry).review_packet(target)
                            status = packet.get("computed_status", "invalid")
                            row = {
                                "target": target,
                                "kind": "semantic",
                                "status": status,
                                "changed_dependencies": packet.get("changed_dependencies", []),
                                "reason_codes": packet.get("reason_codes", []),
                            }
                            if status != "valid":
                                findings.append(self._finding(
                                    "semantic_review_required",
                                    f"semantic target is {status}",
                                    target=target,
                                    details={"reason_codes": row["reason_codes"]},
                                ))
                        else:
                            diff = runtime.diff_receipt(receipt)
                            reasons = set(diff.get("reason_codes", []))
                            if not receipt.audit_complete:
                                reasons.add("audit_incomplete")
                                status = "invalid"
                            elif reasons & {"source_unavailable", "builder_unavailable", "target_unavailable", "semantic_rule_unavailable"}:
                                status = "invalid"
                            else:
                                status = runtime._changed_status(receipt.dependency_type) if diff.get("changed") else "valid"
                            row = {
                                "target": target,
                                "kind": "dependency",
                                "status": status,
                                "changed_dependencies": diff.get("changed_dependencies", []),
                                "reason_codes": sorted(reasons),
                            }
                            if status != "valid":
                                findings.append(self._finding(
                                    "current_dependency_change",
                                    f"current evidence classifies target as {status}",
                                    target=target,
                                    details={"reason_codes": row["reason_codes"]},
                                ))
                        current_checks.append(row)
                    except (DependencyError, ResourceError, SemanticRuleError, BuilderError) as exc:
                        current_checks.append({"target": target, "status": "invalid", "error": str(exc)})
                        findings.append(self._finding("current_target_check_failed", str(exc), target=target))
            except DependencyError as exc:
                findings.append(self._finding("active_receipts_unreadable", str(exc)))
        sections["current_checks"] = current_checks if runtime is not None else {"error": runtime_error}

        # Every registered semantic rule must have a current valid review, including
        # rules that have never produced a receipt/state entry yet.
        semantic_checks: list[dict[str, Any]] = []
        if self.catalog is not None and runtime is not None:
            review_runtime = SemanticReviewRuntime(runtime, self.semantic_registry)
            for rule in self.semantic_registry.rules:
                target = str(rule.target)
                try:
                    packet = review_runtime.review_packet(rule.target)
                    status = packet.get("computed_status", "invalid")
                    semantic_checks.append({
                        "target": target,
                        "rule_id": rule.rule_id,
                        "status": status,
                        "review_context_id": packet.get("review_context_id"),
                    })
                    if status != "valid":
                        findings.append(self._finding(
                            "semantic_review_required",
                            f"semantic target is {status}",
                            target=target,
                            details={"rule_id": rule.rule_id, "reason_codes": packet.get("reason_codes", [])},
                        ))
                except (DependencyError, ResourceError, SemanticRuleError, BuilderError) as exc:
                    semantic_checks.append({"target": target, "rule_id": rule.rule_id, "status": "invalid", "error": str(exc)})
                    findings.append(self._finding("semantic_rule_check_failed", str(exc), target=target))
        elif runtime is None:
            semantic_checks = [
                {"target": str(rule.target), "rule_id": rule.rule_id, "status": "unavailable"}
                for rule in self.semantic_registry.rules
            ]
        sections["semantic_rules"] = semantic_checks

        # Required documentation-owned derived descriptors must have reproducible,
        # auditable builders and a current recorded receipt. Internal-only helper
        # builders are intentionally not release-gated independently.
        builder_checks: list[dict[str, Any]] = []
        if self.catalog is not None:
            active_receipts: dict[str, Any] = {}
            if runtime is not None:
                try:
                    active_receipts = runtime.active_receipts()
                except DependencyError as exc:
                    findings.append(self._finding("active_receipts_unreadable", str(exc)))
            engine = BuildEngine(self.catalog, self.builders)
            for resource in self.catalog.managed:
                if resource.raw.resource_kind != "derived_descriptor":
                    continue
                target_ref = resource.raw.ref
                target = str(target_ref)
                if not self.builders.has_target(target_ref):
                    builder_checks.append({"target": target, "status": "missing_builder"})
                    findings.append(self._finding("required_builder_missing", "derived descriptor has no registered builder", target=target))
                    continue
                try:
                    obj = engine.build(target_ref)
                    receipt = active_receipts.get(target)
                    row = {
                        "target": target,
                        "status": "valid" if runtime is not None else "evidence_unavailable",
                        "audit_complete": obj.provenance.audit_complete,
                        "output_digest": obj.provenance.output_digest,
                        "recorded_receipt_id": None if receipt is None else receipt.receipt_id,
                    }
                    if not obj.provenance.audit_complete:
                        row["status"] = "invalid"
                        findings.append(self._finding("required_builder_audit_incomplete", "builder provenance is incomplete", target=target))
                    if runtime is not None:
                        if receipt is None:
                            row["status"] = "build_required"
                            findings.append(self._finding("required_builder_unrecorded", "derived target has no active build receipt", target=target))
                        elif receipt.output_digest != obj.provenance.output_digest:
                            row["status"] = "build_required"
                            findings.append(self._finding(
                                "required_builder_output_mismatch",
                                "current deterministic output differs from recorded receipt",
                                target=target,
                                details={"recorded": receipt.output_digest, "current": obj.provenance.output_digest},
                            ))
                    builder_checks.append(row)
                except (BuilderError, ResourceError, DependencyError) as exc:
                    builder_checks.append({"target": target, "status": "invalid", "error": str(exc)})
                    findings.append(self._finding("required_builder_failed", str(exc), target=target))
        sections["required_builders"] = builder_checks

        # Generated view parity/drift is a release gate but inspection itself is read-only.
        materialization_section: dict[str, Any]
        if self.catalog is None:
            materialization_section = {"error": "resource catalog unavailable"}
        elif self.renderers is None:
            materialization_section = {"error": "renderer registry unavailable"}
        elif runtime is None:
            materialization_section = {"error": runtime_error or "dependency runtime unavailable"}
        else:
            try:
                materialization = MaterializationRuntime(
                    self.roots,
                    self.catalog,
                    self.builders,
                    self.renderers,
                    runtime,
                )
                materialization_section = materialization.inspect()
                for row in materialization_section.get("outputs", []):
                    if row.get("state") != "current":
                        findings.append(self._finding(
                            "materialization_not_current",
                            f"generated view state is {row.get('state')}",
                            target=f"file://{row.get('path')}",
                            details={k: v for k, v in row.items() if k not in {"path"}},
                        ))
                for orphan in materialization_section.get("orphans", []):
                    if orphan.get("acknowledged"):
                        findings.append(self._finding(
                            "acknowledged_orphan_materialization",
                            "orphaned materialization provenance is acknowledged",
                            severity="warning",
                            target=f"file://{orphan.get('path')}",
                        ))
                    else:
                        findings.append(self._finding(
                            "unresolved_orphan_materialization",
                            "orphaned materialization output requires explicit acknowledgement",
                            target=f"file://{orphan.get('path')}",
                        ))
            except (MaterializationError, ResourceError, BuilderError, DependencyError) as exc:
                materialization_section = {"error": str(exc)}
                findings.append(self._finding("materialization_inspection_failed", str(exc)))
        sections["materialization"] = materialization_section

        findings = self._dedupe(findings)
        blocking = [f for f in findings if f.severity == "blocking"]
        warnings = [f for f in findings if f.severity != "blocking"]
        return {
            "ok": not blocking,
            "summary": {
                "blocking_findings": len(blocking),
                "warnings": len(warnings),
                "total_findings": len(findings),
            },
            "findings": [f.to_dict() for f in findings],
            "sections": sections,
        }


__all__ = ["VerificationFinding", "VerificationRuntime"]
