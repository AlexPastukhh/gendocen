"""Semantic dependency rules and explicit human/AI validation workflow.

P4 deliberately separates structural evidence from semantic judgment. The engine
builds a review packet; a human/AI/CI actor supplies the explicit decision.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .dependencies import (
    ComparatorRegistry,
    DependencyError,
    DependencyReceipt,
    DependencyRuntime,
    DependencyStateEntry,
    ExplicitDependency,
    ReceiptError,
)
from .objects import thaw
from .refs import RefError, ResourceRef


class SemanticRuleError(DependencyError):
    pass


class SemanticValidationError(DependencyError):
    pass


_RULE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SEMANTIC_TYPES = frozenset({"semantic_review", "compatibility", "validity"})
_DECISIONS = frozenset({"still-valid", "updated"})
_ACTOR_KINDS = frozenset({"human", "ai", "ci", "unknown"})


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _stable_hash(prefix: str, value: Any) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical_bytes(value)).hexdigest()}"


@dataclass(frozen=True, slots=True)
class SemanticDependencyRule:
    rule_id: str
    target: ResourceRef
    dependency_type: str
    dependencies: tuple[ExplicitDependency, ...]
    revision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "target": str(self.target),
            "dependency_type": self.dependency_type,
            "revision": self.revision,
            "dependencies": [
                {"source": str(dep.source), "comparator": dep.comparator}
                for dep in self.dependencies
            ],
        }


class SemanticDependencyRegistry:
    """Project-code registry for explicit semantic dependency declarations."""

    def __init__(self) -> None:
        self._by_target: dict[str, SemanticDependencyRule] = {}
        self._by_id: dict[str, SemanticDependencyRule] = {}
        self._comparators = ComparatorRegistry()

    def register(
        self,
        target: ResourceRef | str,
        dependencies: Sequence[ExplicitDependency | tuple[ResourceRef | str, str] | ResourceRef | str],
        *,
        rule_id: str | None = None,
        dependency_type: str = "semantic_review",
    ) -> SemanticDependencyRule:
        target_ref = ResourceRef.parse(target) if isinstance(target, str) else target
        target_s = str(target_ref)
        if dependency_type not in _SEMANTIC_TYPES:
            raise SemanticRuleError(
                f"semantic dependency_type must be one of {sorted(_SEMANTIC_TYPES)}, got {dependency_type!r}"
            )
        if target_s in self._by_target:
            raise SemanticRuleError(f"semantic rule already registered for target {target_s}")

        deps: list[ExplicitDependency] = []
        seen: set[str] = set()
        for item in dependencies:
            if isinstance(item, ExplicitDependency):
                dep = item
            elif isinstance(item, tuple):
                dep = ExplicitDependency.create(item[0], comparator=item[1])
            else:
                dep = ExplicitDependency.create(item)
            self._comparators.validate_id(dep.comparator)
            source_s = str(dep.source)
            if source_s == target_s:
                raise SemanticRuleError(f"semantic rule cannot depend on itself: {target_s}")
            if source_s in seen:
                raise SemanticRuleError(f"duplicate semantic dependency source: {source_s}")
            seen.add(source_s)
            deps.append(dep)
        if not deps:
            raise SemanticRuleError("semantic rule must declare at least one dependency")

        resolved_id = rule_id or f"semantic.{hashlib.sha256(target_s.encode('utf-8')).hexdigest()[:16]}"
        if not isinstance(resolved_id, str) or not _RULE_ID_RE.fullmatch(resolved_id):
            raise SemanticRuleError(
                "rule_id must contain only letters, digits, underscore, dot, colon or hyphen"
            )
        if resolved_id in self._by_id:
            raise SemanticRuleError(f"duplicate semantic rule_id: {resolved_id}")

        definition = {
            "rule_id": resolved_id,
            "target": target_s,
            "dependency_type": dependency_type,
            "dependencies": [
                {"source": str(dep.source), "comparator": dep.comparator}
                for dep in sorted(deps, key=lambda d: str(d.source))
            ],
        }
        revision = "sha256:" + hashlib.sha256(_canonical_bytes(definition)).hexdigest()
        rule = SemanticDependencyRule(
            rule_id=resolved_id,
            target=target_ref,
            dependency_type=dependency_type,
            dependencies=tuple(sorted(deps, key=lambda d: str(d.source))),
            revision=revision,
        )
        self._by_target[target_s] = rule
        self._by_id[resolved_id] = rule
        return rule

    def get(self, target: ResourceRef | str) -> SemanticDependencyRule:
        ref = ResourceRef.parse(target) if isinstance(target, str) else target
        try:
            return self._by_target[str(ref)]
        except KeyError as exc:
            raise SemanticRuleError(f"no semantic dependency rule registered for {ref}") from exc

    def has_target(self, target: ResourceRef | str) -> bool:
        try:
            ref = ResourceRef.parse(target) if isinstance(target, str) else target
        except RefError:
            return False
        return str(ref) in self._by_target

    @property
    def rules(self) -> tuple[SemanticDependencyRule, ...]:
        return tuple(self._by_target[key] for key in sorted(self._by_target))

    def revisions_by_target(self) -> dict[str, tuple[str, str]]:
        return {str(rule.target): (rule.rule_id, rule.revision) for rule in self.rules}

    def validate_cycles(self) -> None:
        targets = set(self._by_target)
        graph = {
            target: tuple(
                sorted(str(dep.source) for dep in rule.dependencies if str(dep.source) in targets)
            )
            for target, rule in self._by_target.items()
        }
        visiting: list[str] = []
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                start = visiting.index(node)
                cycle = visiting[start:] + [node]
                raise SemanticRuleError("semantic dependency cycle detected: " + " -> ".join(cycle))
            visiting.append(node)
            for child in graph.get(node, ()):
                visit(child)
            visiting.pop()
            visited.add(node)

        for node in sorted(graph):
            visit(node)

    def graph_payload(self, target: ResourceRef | str | None = None) -> dict[str, Any]:
        if target is None:
            rules = self.rules
        else:
            rule = self.get(target)
            rules = (rule,)
        edges = [
            {
                "target": str(rule.target),
                "source": str(dep.source),
                "rule_id": rule.rule_id,
                "dependency_type": rule.dependency_type,
                "comparator": dep.comparator,
                "rule_revision": rule.revision,
            }
            for rule in rules
            for dep in rule.dependencies
        ]
        return {"rules": [rule.to_dict() for rule in rules], "rule_edges": edges}


@dataclass(frozen=True, slots=True)
class ValidationContext:
    target: str
    review_context_id: str
    computed_status: str
    rule: Mapping[str, Any]
    target_current: Mapping[str, Any]
    state: Mapping[str, Any] | None
    prior_receipt: Mapping[str, Any] | None
    dependencies: tuple[Mapping[str, Any], ...]
    changed_dependencies: tuple[str, ...]
    reason_codes: tuple[str, ...]
    history: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "review_context_id": self.review_context_id,
            "computed_status": self.computed_status,
            "rule": dict(self.rule),
            "target_current": dict(self.target_current),
            "state": None if self.state is None else dict(self.state),
            "prior_receipt": None if self.prior_receipt is None else dict(self.prior_receipt),
            "dependencies": [dict(item) for item in self.dependencies],
            "changed": bool(self.changed_dependencies or self.reason_codes),
            "changed_dependencies": list(self.changed_dependencies),
            "reason_codes": list(self.reason_codes),
            "history": [dict(event) for event in self.history],
            "semantic_judgment": None,
        }


class SemanticReviewRuntime:
    """Build review packets and record explicit semantic validation decisions."""

    def __init__(self, dependency_runtime: DependencyRuntime, registry: SemanticDependencyRegistry) -> None:
        self.runtime = dependency_runtime
        self.registry = registry

    def _active_receipt(self, target: str) -> DependencyReceipt | None:
        state = self.runtime.state.load()
        entry = state.get("targets", {}).get(target)
        if entry and isinstance(entry.get("last_receipt_id"), str):
            return self.runtime.receipts.load(entry["last_receipt_id"])
        return None

    def _current_target(self, rule: SemanticDependencyRule) -> tuple[Any, str, str]:
        return self.runtime._require_resolver().value_and_version(rule.target)

    def _target_occurrence_revision(self, target: str) -> int:
        """Return the latest persisted state-transition occurrence for one target.

        Receipt IDs and semantic input content are intentionally content-stable, so
        an A -> B -> A cycle can recreate the same prior receipt and dependency
        versions. The occurrence revision keeps a newly-required review distinct
        from an older consumed review of identical content without coupling it to
        unrelated targets' global state changes.
        """
        revisions = [
            event.get("state_revision")
            for event in self.runtime.events.for_target(target)
            if isinstance(event.get("state_revision"), int)
            and not isinstance(event.get("state_revision"), bool)
        ]
        return max(revisions) if revisions else 0

    def review_context(self, target: ResourceRef | str) -> ValidationContext:
        rule = self.registry.get(target)
        target_s = str(rule.target)
        target_value, target_revision, target_kind = self._current_target(rule)
        prior = self._active_receipt(target_s)
        state = self.runtime.state.load().get("targets", {}).get(target_s)
        prior_by_source = {dep.source: dep for dep in prior.dependencies} if prior else {}
        current_by_source = {str(dep.source): dep for dep in rule.dependencies}

        dependency_packets: list[dict[str, Any]] = []
        changed: list[str] = []
        reasons: list[str] = []
        current_versions: list[dict[str, str]] = []

        for dep in rule.dependencies:
            source = str(dep.source)
            current_value, current_version, current_kind = self.runtime._require_resolver().value_and_version(dep.source)
            current_value = thaw(current_value)
            current_versions.append({
                "source": source,
                "version": current_version,
                "comparator": dep.comparator,
            })
            prior_dep = prior_by_source.get(source)
            if prior_dep is None:
                item = {
                    "source": source,
                    "comparator": dep.comparator,
                    "baseline": None,
                    "current": current_value,
                    "current_version": current_version,
                    "current_source_kind": current_kind,
                    "changed": True,
                    "reason": "dependency_added" if prior else "initial_dependency",
                    "diff": None,
                }
                changed.append(source)
                reasons.append(item["reason"])
            else:
                baseline = self.runtime.baselines.load(
                    prior_dep.snapshot_ref,
                    expected_hash=prior_dep.baseline_hash,
                )
                diff = self.runtime.comparators.compare(dep.comparator, baseline.value, current_value)
                item = {
                    "source": source,
                    "comparator": dep.comparator,
                    "baseline": thaw(baseline.value),
                    "current": current_value,
                    "validated_version": prior_dep.observed_version,
                    "current_version": current_version,
                    "current_source_kind": current_kind,
                    "changed": diff.changed,
                    "diff": diff.to_dict(),
                }
                if diff.changed:
                    changed.append(source)
                    reasons.append("dependency_changed")
                if prior_dep.comparator != dep.comparator:
                    item["comparator_changed_from"] = prior_dep.comparator
                    if source not in changed:
                        changed.append(source)
                    reasons.append("dependency_comparator_changed")
            dependency_packets.append(item)

        for source, prior_dep in sorted(prior_by_source.items()):
            if source in current_by_source:
                continue
            baseline = self.runtime.baselines.load(
                prior_dep.snapshot_ref,
                expected_hash=prior_dep.baseline_hash,
            )
            dependency_packets.append({
                "source": source,
                "comparator": prior_dep.comparator,
                "baseline": thaw(baseline.value),
                "current": None,
                "validated_version": prior_dep.observed_version,
                "current_version": None,
                "changed": True,
                "reason": "dependency_removed",
                "diff": None,
            })
            changed.append(source)
            reasons.append("dependency_removed")

        rule_changed = False
        rule_source = f"rule://{rule.rule_id}"
        if prior is not None:
            if prior.semantic_rule_id != rule.rule_id or prior.semantic_rule_revision != rule.revision:
                rule_changed = True
                changed.append(rule_source)
                reasons.append(
                    "semantic_rule_metadata_missing"
                    if prior.semantic_rule_id is None
                    else "semantic_rule_revision_changed"
                )
        else:
            reasons.append("initial_validation_required")

        target_changed = bool(
            prior is not None
            and prior.target_revision is not None
            and prior.target_revision != target_revision
        )
        if target_changed:
            reasons.append("target_changed_since_validation")

        structurally_changed = bool(changed or target_changed or prior is None or rule_changed)
        computed_status = (
            self.runtime._changed_status(rule.dependency_type)
            if structurally_changed
            else "valid"
        )

        context_material = {
            "target": target_s,
            "prior_receipt_id": None if prior is None else prior.receipt_id,
            "target_occurrence_revision": self._target_occurrence_revision(target_s),
            "rule_id": rule.rule_id,
            "rule_revision": rule.revision,
            "target_revision": target_revision,
            "dependencies": sorted(current_versions, key=lambda x: x["source"]),
        }
        context_id = _stable_hash("reviewctx", context_material)
        history = self.runtime.events.for_target(target_s)
        return ValidationContext(
            target=target_s,
            review_context_id=context_id,
            computed_status=computed_status,
            rule=rule.to_dict(),
            target_current={
                "ref": target_s,
                "revision": target_revision,
                "source_kind": target_kind,
                "content": thaw(target_value),
            },
            state=state,
            prior_receipt=None if prior is None else prior.to_dict(),
            dependencies=tuple(sorted(dependency_packets, key=lambda x: x["source"])),
            changed_dependencies=tuple(sorted(set(changed))),
            reason_codes=tuple(sorted(set(reasons))),
            history=history,
        )

    def review_packet(self, target: ResourceRef | str) -> dict[str, Any]:
        return self.review_context(target).to_dict()

    @staticmethod
    def _review_payload(
        *,
        context: ValidationContext,
        rule: SemanticDependencyRule,
        decision: str,
        reason: str,
        evidence: Sequence[str],
        actor_kind: str,
        actor_label: str | None,
    ) -> dict[str, Any]:
        review: dict[str, Any] = {
            "context_id": context.review_context_id,
            "decision": decision,
            "reason": reason,
            "actor_kind": actor_kind,
            "evidence": list(evidence),
            "rule_id": rule.rule_id,
            "rule_revision": rule.revision,
            "prior_receipt_id": None if context.prior_receipt is None else context.prior_receipt["receipt_id"],
        }
        if actor_label is not None:
            review["actor_label"] = actor_label
        return review

    def _consumed_review(self, target: str, context_id: str) -> dict[str, Any] | None:
        matches = [
            event
            for event in self.runtime.events.for_target(target)
            if isinstance(event.get("review"), dict)
            and event["review"].get("context_id") == context_id
        ]
        if len(matches) > 1:
            raise SemanticValidationError(
                f"review context {context_id} appears in multiple events; runtime history is inconsistent"
            )
        if not matches:
            return None
        consumed = matches[0]
        state_entry = self.runtime.state.load().get("targets", {}).get(target)
        target_events = [
            event for event in self.runtime.events.for_target(target)
            if isinstance(event.get("state_revision"), int)
            and not isinstance(event.get("state_revision"), bool)
        ]
        latest_event = max(target_events, key=lambda event: event["state_revision"]) if target_events else None
        # An exact retry is idempotent only while the consumed semantic-validation
        # event is still the active occurrence for this target. If the target later
        # moved through another state and the same content context reappears, this
        # is a new review occurrence and must create a new transition/event.
        if (
            state_entry is not None
            and latest_event is not None
            and latest_event.get("event_id") == consumed.get("event_id")
            and state_entry.get("last_receipt_id") == consumed.get("receipt_id")
            and state_entry.get("status") == consumed.get("status")
        ):
            return consumed
        return None

    def validate(
        self,
        target: ResourceRef | str,
        *,
        result: str,
        reason: str,
        review_context_id: str,
        evidence: Sequence[str] = (),
        actor_kind: str = "unknown",
        actor_label: str | None = None,
    ) -> dict[str, Any]:
        if result not in _DECISIONS:
            raise SemanticValidationError(f"result must be one of {sorted(_DECISIONS)}")
        reason = reason.strip() if isinstance(reason, str) else ""
        if not reason:
            raise SemanticValidationError("semantic validation requires a non-empty reason")
        if actor_kind not in _ACTOR_KINDS:
            raise SemanticValidationError(f"actor_kind must be one of {sorted(_ACTOR_KINDS)}")
        if actor_label is not None:
            actor_label = actor_label.strip()
            if not actor_label:
                raise SemanticValidationError("actor_label must be non-empty when provided")
        cleaned_evidence = tuple(item.strip() for item in evidence if isinstance(item, str) and item.strip())
        if len(cleaned_evidence) != len(tuple(evidence)):
            raise SemanticValidationError("evidence entries must be non-empty strings")
        if not isinstance(review_context_id, str) or not review_context_id:
            raise SemanticValidationError("validate requires review_context_id from the review packet")

        rule = self.registry.get(target)
        consumed = self._consumed_review(str(rule.target), review_context_id)
        if consumed is not None:
            prior_review = consumed["review"]
            requested = {
                "decision": result,
                "reason": reason,
                "actor_kind": actor_kind,
                "evidence": list(cleaned_evidence),
                "rule_id": rule.rule_id,
                "rule_revision": rule.revision,
                "actor_label": actor_label,
            }
            existing = {
                "decision": prior_review["decision"],
                "reason": prior_review["reason"],
                "actor_kind": prior_review["actor_kind"],
                "evidence": prior_review["evidence"],
                "rule_id": prior_review["rule_id"],
                "rule_revision": prior_review["rule_revision"],
                "actor_label": prior_review.get("actor_label"),
            }
            if requested == existing:
                return {
                    "target": consumed["target"],
                    "status": consumed["status"],
                    "receipt_id": consumed["receipt_id"],
                    "event": consumed,
                    "decision": result,
                    "duplicate": True,
                }
            raise SemanticValidationError(
                "review context was already consumed with a different semantic decision payload"
            )

        context = self.review_context(target)
        if context.review_context_id != review_context_id:
            raise SemanticValidationError(
                "review context is stale: target, dependency state or semantic rule changed after review"
            )
        prior = None if context.prior_receipt is None else DependencyReceipt.from_dict(context.prior_receipt)
        target_revision = context.target_current["revision"]
        if context.computed_status == "valid" and prior is not None:
            raise SemanticValidationError("semantic validation is not required for the current unchanged context")
        if result == "still-valid" and prior is not None and prior.target_revision != target_revision:
            raise SemanticValidationError(
                "still-valid cannot accept edited target content; use result='updated' after reviewing the edited target"
            )
        if result == "updated":
            if prior is None:
                raise SemanticValidationError(
                    "updated requires a previously validated target; use still-valid for initial validation"
                )
            if prior.target_revision == target_revision:
                raise SemanticValidationError(
                    "updated requires the target content/state to differ from the previously validated target revision"
                )

        receipt = self.runtime.capture_explicit_receipt(
            rule.target,
            rule.dependencies,
            dependency_type=rule.dependency_type,
            target_revision=target_revision,
            semantic_rule_id=rule.rule_id,
            semantic_rule_revision=rule.revision,
        )
        # Re-capture may observe a concurrent file change. Refuse to activate a
        # receipt that is not exactly the reviewed context. P7 adds locking and
        # multi-file transactions; P4 still refuses known stale review evidence.
        expected_versions = {
            item["source"]: item["current_version"]
            for item in context.dependencies
            if item.get("current_version") is not None and item["source"] in {str(d.source) for d in rule.dependencies}
        }
        actual_versions = {dep.source: dep.observed_version for dep in receipt.dependencies}
        if receipt.target_revision != target_revision or actual_versions != expected_versions:
            raise SemanticValidationError(
                "target or dependencies changed while validation was being recorded; obtain a new review packet"
            )

        review = self._review_payload(
            context=context,
            rule=rule,
            decision=result,
            reason=reason,
            evidence=cleaned_evidence,
            actor_kind=actor_kind,
            actor_label=actor_label,
        )
        entry = DependencyStateEntry("valid", (), receipt.receipt_id, ())
        state, state_changed = self.runtime.state.set_entry(context.target, entry)
        if not state_changed:
            raise SemanticValidationError(
                "validation produced no state change without a matching prior review event; runtime state is inconsistent"
            )
        reason_codes = tuple(sorted(set(context.reason_codes) | {f"semantic_{result}"}))
        event = self.runtime.events.append(
            event_type="semantic_validation",
            target=context.target,
            receipt_id=receipt.receipt_id,
            status="valid",
            changed_dependencies=context.changed_dependencies,
            reason_codes=reason_codes,
            state_revision=state["state_revision"],
            review=review,
        )
        return {
            "target": context.target,
            "status": "valid",
            "receipt_id": receipt.receipt_id,
            "prior_receipt_id": review["prior_receipt_id"],
            "decision": result,
            "reason": reason,
            "actor_kind": actor_kind,
            "actor_label": actor_label,
            "evidence": list(cleaned_evidence),
            "review_context_id": context.review_context_id,
            "event": event,
            "duplicate": False,
        }

    def check_all(self) -> dict[str, Any]:
        state = self.runtime.state.load()
        semantic_targets = {str(rule.target) for rule in self.registry.rules}
        persisted_targets = set(state.get("targets", {})) | set(self.runtime._active_receipts())
        results_by_target: dict[str, dict[str, Any]] = {}

        # Non-semantic targets keep the ordinary P3 classification path. Semantic
        # targets are intentionally excluded here so a rule-type change cannot first
        # create a spurious state/event classified by the old receipt type.
        for target in sorted(persisted_targets - semantic_targets):
            results_by_target[target] = self.runtime.check(target)

        for rule in self.registry.rules:
            target = str(rule.target)
            entry = self.runtime.state.load().get("targets", {}).get(target)
            if entry is None:
                try:
                    context = self.review_context(target)
                except Exception as exc:
                    results_by_target[target] = {
                        "target": target,
                        "status": "invalid",
                        "state_changed": False,
                        "registered_rule_unvalidated": True,
                        "diff": {
                            "target": target,
                            "changed": True,
                            "changed_dependencies": [],
                            "reason_codes": ["semantic_rule_input_unavailable"],
                            "error": str(exc),
                        },
                    }
                else:
                    results_by_target[target] = {
                        "target": target,
                        "status": context.computed_status,
                        "state_changed": False,
                        "registered_rule_unvalidated": True,
                        "review_context_id": context.review_context_id,
                        "diff": {
                            "target": target,
                            "changed": True,
                            "changed_dependencies": list(context.changed_dependencies),
                            "reason_codes": list(context.reason_codes),
                        },
                    }
                continue

            receipt = self.runtime.receipts.load(entry["last_receipt_id"])
            if receipt.semantic_rule_id is None:
                required_status = self.runtime._changed_status(rule.dependency_type)
                replacement = DependencyStateEntry(
                    required_status,
                    (),
                    receipt.receipt_id,
                    ("semantic_rule_metadata_missing",),
                )
                new_state, changed = self.runtime.state.set_entry(target, replacement)
                if changed:
                    self.runtime.events.append(
                        event_type=f"semantic_rule_{required_status}",
                        target=target,
                        receipt_id=receipt.receipt_id,
                        status=required_status,
                        changed_dependencies=(),
                        reason_codes=("semantic_rule_metadata_missing",),
                        state_revision=new_state["state_revision"],
                    )
                results_by_target[target] = {
                    "target": target,
                    "status": required_status,
                    "state_changed": changed,
                    "diff": {
                        "target": target,
                        "changed": True,
                        "changed_dependencies": [],
                        "reason_codes": ["semantic_rule_metadata_missing"],
                    },
                }
                continue

            results_by_target[target] = self.runtime.check(
                target,
                dependency_type_override=rule.dependency_type,
            )

        results = [results_by_target[k] for k in sorted(results_by_target)]
        counts: dict[str, int] = {}
        for item in results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"results": results, "counts": dict(sorted(counts.items())), "checked": len(results)}

    def graph(self, target: ResourceRef | str | None = None) -> dict[str, Any]:
        persisted = self.runtime.graph(target)
        rules = self.registry.graph_payload(target)
        return {**persisted, **rules}


__all__ = [
    "SemanticDependencyRegistry",
    "SemanticDependencyRule",
    "SemanticReviewRuntime",
    "SemanticRuleError",
    "SemanticValidationError",
    "ValidationContext",
]
