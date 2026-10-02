"""Command-line interface for the Generic Documentation Engine."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .output import CommandResult, Issue
from .project import (
    ProjectInitializationError,
    RootDiscoveryError,
    discover_roots,
    initialize_project,
)
from .resources import ResourceCatalog, ResourceError
from .refs import RefError
from .builders import BuilderError, BuilderRegistry
from .dependencies import DependencyError, DependencyRuntime
from .extensions import ProjectExtensionError, load_project_extension
from .semantic import SemanticDependencyRegistry, SemanticReviewRuntime, SemanticRuleError, SemanticValidationError
from .materialization import MaterializationError, MaterializationRuntime, RendererRegistry, SyncRuntime
from .verification import VerificationFinding, VerificationRuntime
from .versions import ENGINE_VERSION
from .hardening import (
    FileTransaction, HardeningError, HardeningManager, LockBusyError, LockManager,
    MigrationError, MigrationManager, RecoveryRequiredError,
)

EXIT_SUCCESS = 0
EXIT_ATTENTION_REQUIRED = 2
EXIT_DOMAIN_FAILURE = 3
EXIT_USAGE_OR_CONFIG = 4
EXIT_INTERNAL_FAILURE = 5


class CliUsageError(ValueError):
    pass


class DocengineArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised through main
        raise CliUsageError(message)


COMMANDS = (
    "init",
    "status",
    "check",
    "diff",
    "explain",
    "sync",
    "rebuild",
    "validate",
    "materialize",
    "verify",
    "history",
    "graph",
    "recover",
    "migrate",
    "resources",
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit versioned JSON envelope")
    parser.add_argument("--project-root", help="explicit project root")
    parser.add_argument("--docs-root", help="explicit documentation root (absolute or project-relative)")


def build_parser() -> argparse.ArgumentParser:
    parser = DocengineArgumentParser(prog="docengine", description="Generic Documentation Engine")
    parser.add_argument("--version", action="version", version=f"%(prog)s {ENGINE_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=DocengineArgumentParser)
    for command in COMMANDS:
        sub = subparsers.add_parser(command, help=f"{command} command")
        _add_common_options(sub)
        if command in {"diff", "explain", "rebuild", "validate", "materialize", "history", "graph"}:
            sub.add_argument("target", nargs="?", help="target resource")
        if command == "sync":
            sub.add_argument(
                "--all", action="store_true", dest="all_targets",
                help="materialize all registered views; deterministic rebuild selection remains evidence-driven",
            )
        if command == "recover":
            sub.add_argument("--force", action="store_true", help="force rollback even when transaction targets changed after the crash")
        if command == "materialize":
            sub.add_argument("--all", action="store_true", dest="all_targets", help="materialize all registered views")
            sub.add_argument(
                "--ack-orphan", action="store_true", dest="ack_orphan",
                help="acknowledge orphaned materialization state for TARGET while preserving provenance and the file",
            )
        if command == "validate":
            sub.add_argument("--result")
            sub.add_argument("--reason")
            sub.add_argument("--review-context", dest="review_context")
            sub.add_argument("--actor-kind", default="unknown")
            sub.add_argument("--actor-label")
            sub.add_argument("--evidence", action="append", default=[])
    return parser


def _execute_init(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        outcome = initialize_project(project_root=args.project_root, docs_root=args.docs_root)
    except (ProjectInitializationError, RootDiscoveryError) as exc:
        return CommandResult(
            command="init",
            ok=False,
            status="init_failed",
            issues=(Issue(code="init_failed", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG
    status = "initialized" if outcome.changed else "already_initialized"
    return CommandResult(
        command="init",
        ok=True,
        status=status,
        data={
            "roots": outcome.roots.to_dict(),
            "created": list(outcome.created),
            "existing": list(outcome.existing),
        },
    ), EXIT_SUCCESS


def _execute_resources(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        roots = discover_roots(project_root=args.project_root, docs_root=args.docs_root)
        catalog = ResourceCatalog.scan(roots)
    except (RootDiscoveryError, ResourceError) as exc:
        return CommandResult(
            command="resources",
            ok=False,
            status="resource_scan_failed",
            issues=(Issue(code="resource_scan_failed", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG
    return CommandResult(command="resources", ok=True, status="ok", data=catalog.to_payload()), EXIT_SUCCESS


def _runtime_for(
    args: argparse.Namespace,
    *,
    need_catalog: bool,
    need_builders: bool,
    need_renderers: bool = False,
) -> tuple[DependencyRuntime, object, SemanticDependencyRegistry, RendererRegistry]:
    roots = discover_roots(project_root=args.project_root, docs_root=args.docs_root)
    semantic_registry = SemanticDependencyRegistry()
    renderer_registry = RendererRegistry()
    if not need_catalog:
        return DependencyRuntime(roots), roots, semantic_registry, renderer_registry
    catalog = ResourceCatalog.scan(roots)
    registry = BuilderRegistry()
    builder_load_error = None
    if need_builders:
        package_dir = roots.project_root.joinpath(*roots.config.project_package.split("."))
        if package_dir.is_dir():
            try:
                extension = load_project_extension(roots, catalog, include_renderers=need_renderers)
                registry = extension.registry
                semantic_registry = extension.semantic_registry
                renderer_registry = extension.renderer_registry
            except (ProjectExtensionError, SemanticRuleError, BuilderError, MaterializationError) as exc:
                # Persisted diagnostics remain readable when current project code is
                # broken. Current builder/rule verification then surfaces explicit
                # unavailable diagnostics rather than hiding prior state/history.
                builder_load_error = str(exc)
    runtime = DependencyRuntime(
        roots,
        catalog,
        registry,
        semantic_rule_revisions=semantic_registry.revisions_by_target(),
    )
    runtime.builder_load_error = builder_load_error
    return runtime, roots, semantic_registry, renderer_registry


def _execute_dependency_command(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        need_catalog = args.command in {"check", "diff", "explain", "graph"}
        need_builders = args.command in {"check", "diff", "explain", "graph"}
        runtime, roots, semantic_registry, _ = _runtime_for(args, need_catalog=need_catalog, need_builders=need_builders)
        if args.command == "status":
            data = runtime.status()
        elif args.command == "check":
            if semantic_registry.rules:
                data = SemanticReviewRuntime(runtime, semantic_registry).check_all()
            else:
                data = runtime.check_all()
        elif args.command == "diff":
            data = runtime.diff(args.target)
        elif args.command == "explain":
            if semantic_registry.has_target(args.target):
                data = SemanticReviewRuntime(runtime, semantic_registry).review_packet(args.target)
            else:
                data = runtime.explain(args.target)
        elif args.command == "history":
            data = runtime.history(args.target)
        elif args.command == "graph":
            if args.target is not None and semantic_registry.has_target(args.target):
                data = SemanticReviewRuntime(runtime, semantic_registry).graph(args.target)
            elif args.target is None and semantic_registry.rules:
                data = SemanticReviewRuntime(runtime, semantic_registry).graph()
            else:
                data = runtime.graph(args.target)
        else:
            raise AssertionError(args.command)
    except (RootDiscoveryError, ResourceError, ProjectExtensionError, RefError) as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="usage_or_config_error",
            issues=(Issue(code="usage_or_config_error", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG
    except (DependencyError, MaterializationError) as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="domain_failure",
            issues=(Issue(code="domain_failure", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    diagnostics = []
    if getattr(runtime, "builder_load_error", None):
        diagnostics.append({"code": "builder_registry_unavailable", "message": runtime.builder_load_error})
    ok, attention, exit_code = _dependency_result_policy(args.command, data)
    status = "ok" if ok else "domain_failure"
    issues: tuple[Issue, ...] = ()
    if diagnostics:
        if args.command in {"check", "diff", "explain"}:
            ok = False
            attention = True
            exit_code = EXIT_DOMAIN_FAILURE
            status = "current_project_code_unavailable"
        else:
            issues = tuple(
                Issue(code=item["code"], message=item["message"], severity="warning")
                for item in diagnostics
            )
    return CommandResult(
        command=args.command,
        ok=ok,
        status=status,
        attention_required=attention,
        data={"roots": roots.to_dict(), **data, "runtime_diagnostics": diagnostics},
        issues=issues,
    ), exit_code


def _execute_validate(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        runtime, roots, semantic_registry, _ = _runtime_for(args, need_catalog=True, need_builders=True)
        if getattr(runtime, "builder_load_error", None):
            raise SemanticValidationError(
                f"current project builder/semantic registry is unavailable: {runtime.builder_load_error}"
            )
        review = SemanticReviewRuntime(runtime, semantic_registry)
        data = review.validate(
            args.target,
            result=args.result,
            reason=args.reason,
            review_context_id=args.review_context,
            evidence=tuple(args.evidence or ()),
            actor_kind=args.actor_kind,
            actor_label=args.actor_label,
        )
    except (RootDiscoveryError, ResourceError, ProjectExtensionError, RefError) as exc:
        return CommandResult(
            command="validate",
            ok=False,
            status="usage_or_config_error",
            issues=(Issue(code="usage_or_config_error", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG
    except (DependencyError, SemanticRuleError, SemanticValidationError, MaterializationError) as exc:
        return CommandResult(
            command="validate",
            ok=False,
            status="validation_failed",
            issues=(Issue(code="validation_failed", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    return CommandResult(
        command="validate",
        ok=True,
        status="validated",
        data={"roots": roots.to_dict(), **data},
    ), EXIT_SUCCESS


def _execute_p5_command(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        runtime, roots, semantic_registry, renderer_registry = _runtime_for(
            args, need_catalog=True, need_builders=True, need_renderers=True
        )
        if runtime.catalog is None:
            raise MaterializationError("resource catalog unavailable")
        if getattr(runtime, "builder_load_error", None):
            raise MaterializationError(
                f"current project builder/semantic/renderer registry is unavailable: {runtime.builder_load_error}"
            )
        materialization = MaterializationRuntime(
            roots, runtime.catalog, runtime.registry, renderer_registry, runtime
        )
        sync_runtime = SyncRuntime(runtime, semantic_registry, materialization)
        if args.command == "materialize":
            if bool(getattr(args, "ack_orphan", False)):
                data = materialization.acknowledge_orphan(args.target)
                status = "orphan_acknowledged"
            else:
                data = materialization.materialize(args.target, all_targets=bool(args.all_targets))
                status = "materialized"
            ok = True
            exit_code = 0
        elif args.command == "rebuild":
            data = sync_runtime.rebuild(args.target)
            # Derived object itself is an in-memory implementation detail, not CLI JSON.
            data.pop("object", None)
            status = "rebuilt"
            ok = data.get("status") != "invalid"
            exit_code = EXIT_SUCCESS if ok else EXIT_DOMAIN_FAILURE
        elif args.command == "sync":
            data = sync_runtime.sync(all_targets=bool(args.all_targets))
            status = str(data.get("status", "ok"))
            ok = bool(data.get("ok", False))
            if not ok:
                exit_code = EXIT_DOMAIN_FAILURE
            elif status == "attention_required":
                exit_code = EXIT_ATTENTION_REQUIRED
            else:
                exit_code = EXIT_SUCCESS
        else:
            raise AssertionError(args.command)
    except (RootDiscoveryError, ResourceError, ProjectExtensionError, RefError) as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="usage_or_config_error",
            issues=(Issue(code="usage_or_config_error", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG
    except (DependencyError, SemanticRuleError, MaterializationError) as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status=f"{args.command}_failed",
            issues=(Issue(code=f"{args.command}_failed", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    attention = bool(status == "attention_required")
    return CommandResult(
        command=args.command,
        ok=ok,
        status=status,
        attention_required=attention,
        data={"roots": roots.to_dict(), **data},
    ), exit_code


def _execute_verify(args: argparse.Namespace) -> tuple[CommandResult, int]:
    try:
        roots = discover_roots(project_root=args.project_root, docs_root=args.docs_root)
    except RootDiscoveryError as exc:
        return CommandResult(
            command="verify",
            ok=False,
            status="invalid_configuration",
            issues=(Issue(code="invalid_configuration", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG

    component_findings: list[VerificationFinding] = []
    hardening_section: dict[str, object] = {}
    try:
        hardening_manager = HardeningManager(roots)
        pending = hardening_manager.pending_transactions()
        recovery_history = hardening_manager.recovery_history()
        migration_manager = MigrationManager(roots)
        migration = migration_manager.inspect()
        hardening_section = {
            "pending_transactions": pending,
            "recovery_event_count": len(recovery_history),
            "migration": migration,
        }
        interrupted = [item for item in pending if not item.get("cleanup_only")]
        cleanup_only = [item for item in pending if item.get("cleanup_only")]
        if interrupted:
            component_findings.append(VerificationFinding(
                code="recovery_required",
                severity="blocking",
                message=f"{len(interrupted)} interrupted transaction(s) require 'docengine recover'",
                details={"transactions": [item.get("transaction_id") for item in interrupted]},
            ))
        if cleanup_only:
            component_findings.append(VerificationFinding(
                code="transaction_cleanup_required",
                severity="warning",
                message=f"{len(cleanup_only)} committed transaction journal(s) await cleanup",
                details={"transactions": [item.get("transaction_id") for item in cleanup_only]},
            ))
        if migration.get("migration_required"):
            component_findings.append(VerificationFinding(
                code="migration_required",
                severity="blocking",
                message="persisted runtime layout must be migrated with 'docengine migrate'",
                details={"from_version": migration.get("version"), "to_version": migration.get("target_version")},
            ))
    except HardeningError as exc:
        hardening_section = {"error": str(exc)}
        component_findings.append(VerificationFinding(
            code="hardening_runtime_unavailable",
            severity="blocking",
            message=str(exc),
        ))

    catalog = None
    builders = BuilderRegistry()
    semantic_registry = SemanticDependencyRegistry()
    renderer_registry: RendererRegistry | None = RendererRegistry()

    try:
        catalog = ResourceCatalog.scan(roots)
    except ResourceError as exc:
        component_findings.append(VerificationFinding(
            code="resource_catalog_invalid",
            severity="blocking",
            message=str(exc),
        ))

    if catalog is not None:
        package_dir = roots.project_root.joinpath(*roots.config.project_package.split("."))
        if package_dir.is_dir():
            try:
                base_extension = load_project_extension(roots, catalog, include_renderers=False)
                builders = base_extension.registry
                semantic_registry = base_extension.semantic_registry
            except (ProjectExtensionError, SemanticRuleError, BuilderError, MaterializationError) as exc:
                component_findings.append(VerificationFinding(
                    code="project_extension_invalid",
                    severity="blocking",
                    message=str(exc),
                ))
            else:
                try:
                    rendered_extension = load_project_extension(roots, catalog, include_renderers=True)
                    renderer_registry = rendered_extension.renderer_registry
                except (ProjectExtensionError, SemanticRuleError, BuilderError, MaterializationError) as exc:
                    component_findings.append(VerificationFinding(
                        code="renderer_registry_invalid",
                        severity="blocking",
                        message=str(exc),
                    ))

    report = VerificationRuntime(
        roots,
        catalog=catalog,
        builders=builders,
        semantic_registry=semantic_registry,
        renderers=renderer_registry,
        component_errors=component_findings,
    ).run()
    report.setdefault("sections", {})["hardening"] = hardening_section
    ok = bool(report.get("ok", False))
    return CommandResult(
        command="verify",
        ok=ok,
        status="verified" if ok else "verification_failed",
        attention_required=not ok,
        data={"roots": roots.to_dict(), "report": report},
    ), EXIT_SUCCESS if ok else EXIT_DOMAIN_FAILURE


def _validate_cli_usage(args: argparse.Namespace) -> None:
    command = args.command
    target = getattr(args, "target", None)
    if command in {"diff", "explain", "rebuild", "history"} and not target:
        raise CliUsageError(f"{command} requires TARGET")
    if command == "validate":
        if not target:
            raise CliUsageError("validate requires TARGET")
        if args.result not in {"still-valid", "updated"}:
            raise CliUsageError("validate --result must be still-valid or updated")
        if not isinstance(args.reason, str) or not args.reason.strip():
            raise CliUsageError("validate requires non-empty --reason")
        if not isinstance(args.review_context, str) or not args.review_context.strip():
            raise CliUsageError("validate requires --review-context")
        if args.actor_kind not in {"human", "ai", "ci", "unknown"}:
            raise CliUsageError("validate --actor-kind must be human, ai, ci, or unknown")
    if command == "materialize":
        if bool(getattr(args, "ack_orphan", False)) and bool(getattr(args, "all_targets", False)):
            raise CliUsageError("materialize --ack-orphan and --all are mutually exclusive")
        if bool(getattr(args, "ack_orphan", False)) and not target:
            raise CliUsageError("materialize --ack-orphan requires TARGET")
        if not target and not bool(getattr(args, "all_targets", False)):
            raise CliUsageError("materialize requires TARGET or --all")
        if target and bool(getattr(args, "all_targets", False)):
            raise CliUsageError("materialize TARGET and --all are mutually exclusive")


def _dependency_result_policy(command: str, data: dict[str, object]) -> tuple[bool, bool, int]:
    """Return (ok, attention_required, exit_code) for completed query/check facts."""
    if command in {"history", "graph"}:
        return True, False, EXIT_SUCCESS
    if command == "status":
        counts = data.get("counts", {}) if isinstance(data, dict) else {}
        invalid = int(counts.get("invalid", 0)) if isinstance(counts, dict) else 0
        attention = sum(int(counts.get(key, 0)) for key in ("stale", "review_required", "build_required")) if isinstance(counts, dict) else 0
        if invalid:
            return False, True, EXIT_DOMAIN_FAILURE
        if attention:
            return True, True, EXIT_ATTENTION_REQUIRED
        return True, False, EXIT_SUCCESS
    if command == "check":
        counts = data.get("counts", {}) if isinstance(data, dict) else {}
        invalid = int(counts.get("invalid", 0)) if isinstance(counts, dict) else 0
        attention = sum(int(counts.get(key, 0)) for key in ("stale", "review_required", "build_required")) if isinstance(counts, dict) else 0
        if invalid:
            return False, True, EXIT_DOMAIN_FAILURE
        if attention:
            return True, True, EXIT_ATTENTION_REQUIRED
        return True, False, EXIT_SUCCESS
    if command == "diff":
        changed = bool(data.get("changed"))
        reasons = set(data.get("reason_codes", [])) if isinstance(data.get("reason_codes", []), list) else set()
        if reasons & {"source_unavailable", "builder_unavailable", "target_unavailable"}:
            return False, True, EXIT_DOMAIN_FAILURE
        return True, changed, EXIT_ATTENTION_REQUIRED if changed else EXIT_SUCCESS
    if command == "explain":
        status = data.get("computed_status")
        if status is None and isinstance(data.get("state"), dict):
            status = data["state"].get("status")
        if status == "invalid":
            return False, True, EXIT_DOMAIN_FAILURE
        if status in {"stale", "review_required", "build_required"}:
            return True, True, EXIT_ATTENTION_REQUIRED
        current_diff = data.get("current_diff")
        if isinstance(current_diff, dict) and current_diff.get("changed"):
            return True, True, EXIT_ATTENTION_REQUIRED
        return True, False, EXIT_SUCCESS
    return True, False, EXIT_SUCCESS


def _execute_recover(args: argparse.Namespace, roots, manager: HardeningManager) -> tuple[CommandResult, int]:
    data = manager.recover(force=bool(getattr(args, "force", False)))
    return CommandResult(
        command="recover",
        ok=True,
        status="recovered" if data.get("recovered") else "recovery_not_needed",
        data={"roots": roots.to_dict(), **data},
    ), EXIT_SUCCESS


def _execute_migrate(args: argparse.Namespace, roots, manager: HardeningManager) -> tuple[CommandResult, int]:
    data = MigrationManager(roots).migrate()
    return CommandResult(
        command="migrate",
        ok=True,
        status="migrated" if data.get("changed") else "migration_not_needed",
        data={"roots": roots.to_dict(), **data},
    ), EXIT_SUCCESS


_READ_ONLY_COMMANDS = {"status", "diff", "explain", "history", "graph", "resources", "verify"}
_TRANSACTIONAL_COMMANDS = {"check", "sync", "rebuild", "validate", "materialize"}


def _execute_with_hardening(args: argparse.Namespace) -> tuple[CommandResult, int]:
    # Project initialization predates the documentation runtime. Its config writes
    # remain P1 semantics; runtime locking begins once project/docs roots exist.
    if args.command == "init":
        return _execute(args)
    try:
        roots = discover_roots(project_root=args.project_root, docs_root=args.docs_root)
    except RootDiscoveryError as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="usage_or_config_error",
            issues=(Issue(code="usage_or_config_error", message=str(exc)),),
        ), EXIT_USAGE_OR_CONFIG

    # verify must turn unsafe/corrupt runtime ownership into report findings rather
    # than failing before its complete-report engine can run.
    if args.command == "verify":
        try:
            with LockManager(roots).held(shared=True):
                return _execute(args)
        except LockBusyError as exc:
            return CommandResult(
                command=args.command,
                ok=False,
                status="runtime_busy",
                attention_required=True,
                issues=(Issue(code="runtime_busy", message=str(exc)),),
            ), EXIT_DOMAIN_FAILURE

    try:
        manager = HardeningManager(roots)
        if args.command == "recover":
            with manager.lock_manager.held(shared=False):
                return _execute_recover(args, roots, manager)
        if args.command == "migrate":
            with manager.lock_manager.held(shared=False):
                recovery = manager.recover()
                with FileTransaction(roots, "migrate"):
                    result, code = _execute_migrate(args, roots, manager)
                if recovery.get("recovered"):
                    result = CommandResult(
                        command=result.command,
                        ok=result.ok,
                        status=result.status,
                        attention_required=result.attention_required,
                        data={**result.data, "recovery_before_migration": recovery},
                        issues=result.issues,
                    )
                return result, code
        if args.command in _READ_ONLY_COMMANDS:
            with manager.read_guard():
                return _execute(args)
        if args.command in _TRANSACTIONAL_COMMANDS:
            with manager.lock_manager.held(shared=False):
                recovery = manager.recover()
                migration = MigrationManager(roots).inspect()
                with FileTransaction(roots, args.command):
                    migration_result = None
                    if migration.get("migration_required") or migration.get("implicit_empty"):
                        migration_result = MigrationManager(roots).migrate()
                    result, code = _execute(args)
                if migration_result and migration_result.get("changed"):
                    result = CommandResult(
                        command=result.command,
                        ok=result.ok,
                        status=result.status,
                        attention_required=result.attention_required,
                        data={**result.data, "migration_before_command": migration_result},
                        issues=result.issues,
                    )
                if recovery.get("recovered"):
                    result = CommandResult(
                        command=result.command,
                        ok=result.ok,
                        status=result.status,
                        attention_required=result.attention_required,
                        data={**result.data, "recovery_before_command": recovery},
                        issues=result.issues,
                    )
                return result, code
        return _execute(args)
    except LockBusyError as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="runtime_busy",
            attention_required=True,
            issues=(Issue(code="runtime_busy", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    except RecoveryRequiredError as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="recovery_required",
            attention_required=True,
            issues=(Issue(code="recovery_required", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    except MigrationError as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="migration_failed",
            attention_required=True,
            issues=(Issue(code="migration_failed", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE
    except HardeningError as exc:
        return CommandResult(
            command=args.command,
            ok=False,
            status="hardening_failure",
            attention_required=True,
            issues=(Issue(code="hardening_failure", message=str(exc)),),
        ), EXIT_DOMAIN_FAILURE


def _execute(args: argparse.Namespace) -> tuple[CommandResult, int]:
    if args.command == "init":
        return _execute_init(args)
    if args.command == "resources":
        return _execute_resources(args)
    if args.command in {"status", "check", "diff", "explain", "history", "graph"}:
        return _execute_dependency_command(args)
    if args.command == "validate":
        return _execute_validate(args)
    if args.command in {"rebuild", "materialize", "sync"}:
        return _execute_p5_command(args)
    if args.command == "verify":
        return _execute_verify(args)
    if args.command in {"recover", "migrate"}:
        raise AssertionError(f"{args.command} must run through P7 hardening guard")

    try:
        roots = discover_roots(project_root=args.project_root, docs_root=args.docs_root)
    except RootDiscoveryError as exc:
        result = CommandResult(
            command=args.command,
            ok=False,
            status="invalid_roots",
            issues=(Issue(code="invalid_roots", message=str(exc)),),
        )
        return result, EXIT_USAGE_OR_CONFIG

    result = CommandResult(
        command=args.command,
        ok=False,
        status="not_implemented",
        data={"roots": roots.to_dict()},
        issues=(
            Issue(
                code="phase_not_implemented",
                message=f"'{args.command}' behavior is not implemented yet; current implementation is complete through P7.",
                severity="info",
            ),
        ),
    )
    return result, EXIT_INTERNAL_FAILURE


def _render_human(result: CommandResult) -> str:
    if result.command == "resources" and result.ok:
        data = result.data
        lines = ["docengine resources: ok"]
        roots = data.get("roots", {})
        lines.append(f"documentation_root: {roots.get('documentation_root')}")
        for item in data.get("resources", []):
            suffix = ""
            if "owner_ref" in item:
                suffix = f" owner={item['owner_ref']}"
            lines.append(f"{item['kind'].upper():9} {item['ref']}{suffix}")
        counts = data.get("counts", {})
        lines.append("counts: " + ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))
        return "\n".join(lines)

    if result.command in {"status", "check", "diff", "explain", "history", "graph"} and (result.ok or result.data):
        lines = [f"docengine {result.command}: {result.status}"]
        if result.command == "status":
            counts = result.data.get("counts", {})
            lines.append("counts: " + ", ".join(f"{k}={counts[k]}" for k in sorted(counts)) if counts else "counts: empty")
            for target, entry in sorted(result.data.get("targets", {}).items()):
                lines.append(f"{entry.get('status','?').upper():15} {target}")
        elif result.command == "check":
            counts = result.data.get("counts", {})
            lines.append(f"checked: {result.data.get('checked', 0)}")
            if counts:
                lines.append("counts: " + ", ".join(f"{k}={counts[k]}" for k in sorted(counts)))
            for item in result.data.get("results", []):
                lines.append(f"{item['status'].upper():15} {item['target']}")
        else:
            payload = {k: v for k, v in result.data.items() if k != "roots"}
            if payload:
                lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        for issue in result.issues:
            lines.append(f"{issue.severity}: {issue.message}")
        return "\n".join(lines)

    if result.command in {"rebuild", "materialize", "sync", "recover", "migrate"} and (result.ok or result.data):
        lines = [f"docengine {result.command}: {result.status}"]
        payload = {k: v for k, v in result.data.items() if k != "roots"}
        if payload:
            lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        for issue in result.issues:
            lines.append(f"{issue.severity}: {issue.message}")
        return "\n".join(lines)

    if result.command == "validate" and result.ok:
        lines = [f"docengine validate: {result.status}"]
        lines.append(f"target: {result.data.get('target')}")
        lines.append(f"decision: {result.data.get('decision')}")
        lines.append(f"receipt_id: {result.data.get('receipt_id')}")
        if result.data.get("duplicate"):
            lines.append("duplicate: true")
        return "\n".join(lines)

    if result.command == "verify" and isinstance(result.data, dict) and isinstance(result.data.get("report"), dict):
        report = result.data["report"]
        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        lines = [f"docengine verify: {result.status}"]
        lines.append(f"blocking_findings: {summary.get('blocking_findings', 0)}")
        lines.append(f"warnings: {summary.get('warnings', 0)}")
        for finding in report.get("findings", []) if isinstance(report, dict) else []:
            target = f" {finding.get('target')}" if finding.get("target") else ""
            lines.append(f"{str(finding.get('severity','?')).upper():8} {finding.get('code')}{target}: {finding.get('message')}")
        for issue in result.issues:
            lines.append(f"{issue.severity}: {issue.message}")
        return "\n".join(lines)

    if result.command == "init" and result.ok:
        roots = result.data.get("roots", {})
        lines = [f"docengine init: {result.status}"]
        lines.append(f"project_root: {roots.get('project_root')}")
        lines.append(f"documentation_root: {roots.get('documentation_root')}")
        if result.data.get("created"):
            lines.append("created: " + ", ".join(result.data["created"]))
        return "\n".join(lines)

    roots = result.data.get("roots", {})
    lines = [f"docengine {result.command}: {result.status}"]
    if roots:
        lines.extend([
            f"project_root: {roots.get('project_root')}",
            f"documentation_root: {roots.get('documentation_root')}",
        ])
    for issue in result.issues:
        lines.append(f"{issue.severity}: {issue.message}")
    return "\n".join(lines)


def _command_hint(argv: Sequence[str]) -> str:
    for token in argv:
        if token in COMMANDS:
            return token
        if not token.startswith("-"):
            return token
    return "cli"


def _emit(result: CommandResult, exit_code: int, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result.to_dict(exit_code=exit_code), ensure_ascii=False, sort_keys=True))
    else:
        print(_render_human(result))


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_requested = "--json" in raw_argv
    parser = build_parser()
    try:
        args = parser.parse_args(raw_argv)
        _validate_cli_usage(args)
    except CliUsageError as exc:
        result = CommandResult(
            command=_command_hint(raw_argv),
            ok=False,
            status="usage_error",
            issues=(Issue(code="usage_error", message=str(exc)),),
        )
        _emit(result, EXIT_USAGE_OR_CONFIG, json_output=json_requested)
        return EXIT_USAGE_OR_CONFIG

    try:
        result, exit_code = _execute_with_hardening(args)
    except Exception as exc:  # last-resort protocol boundary; never emit traceback in normal CLI mode
        result = CommandResult(
            command=args.command,
            ok=False,
            status="internal_error",
            issues=(Issue(code="internal_error", message=str(exc)),),
        )
        exit_code = EXIT_INTERNAL_FAILURE
    _emit(result, exit_code, json_output=args.json_output)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
