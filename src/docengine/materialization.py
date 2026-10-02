"""P5 renderers, generated-view materialization, drift detection and sync orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .builders import BuildEngine, BuilderError, BuilderRegistry, DerivedObject
from .dependencies import DependencyError, DependencyReceipt, DependencyRuntime
from .objects import RawObject, thaw
from .project import ProjectRoots, RootDiscoveryError, confined_path, is_within
from .refs import RefError, ResourceRef
from .resources import ManagedResource, MaterializationTarget, ResourceCatalog, ResourceError
from .semantic import SemanticDependencyRegistry, SemanticReviewRuntime
from .versions import PERSISTED_STATE_SCHEMA_VERSION
from .hardening import HardeningError, atomic_write_bytes as _hardened_atomic_write_bytes, atomic_write_text as _hardened_atomic_write_text


class MaterializationError(RuntimeError):
    pass


class RendererRegistrationError(MaterializationError):
    pass


class RendererExecutionError(MaterializationError):
    pass


_RENDERER_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_BUILTIN_MARKDOWN_REVISION = "builtin:markdown:v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _label(value: str) -> str:
    text = re.sub(r"[_\-.]+", " ", value).strip()
    return text[:1].upper() + text[1:] if text else value


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


@dataclass(frozen=True, slots=True)
class RenderContext:
    owner_ref: ResourceRef
    resource_id: str
    resource_kind: str
    target_path: str
    renderer_id: str


RendererFunction = Callable[[Any, RenderContext], str | bytes]


@dataclass(frozen=True, slots=True)
class RendererSpec:
    renderer_id: str
    function: RendererFunction
    revision: str


class RendererRegistry:
    """Renderer registry with one deterministic built-in Markdown renderer."""

    def __init__(self, *, source_revision: str = "unversioned") -> None:
        if not isinstance(source_revision, str) or not source_revision.strip():
            raise RendererRegistrationError("source_revision must be a non-empty string")
        self.source_revision = source_revision.strip()
        self._specs: dict[str, RendererSpec] = {
            "markdown": RendererSpec("markdown", render_markdown, _BUILTIN_MARKDOWN_REVISION)
        }

    def register(
        self,
        renderer_id: str,
        function: RendererFunction,
        *,
        revision: str | None = None,
        replace: bool = False,
    ) -> RendererSpec:
        if not isinstance(renderer_id, str) or not _RENDERER_ID_RE.fullmatch(renderer_id):
            raise RendererRegistrationError("renderer_id must be a canonical non-empty identifier")
        if not callable(function):
            raise RendererRegistrationError("renderer function must be callable")
        if renderer_id in self._specs and not replace:
            raise RendererRegistrationError(f"renderer already registered: {renderer_id}")
        resolved_revision = revision or self.source_revision
        if not isinstance(resolved_revision, str) or not resolved_revision.strip():
            raise RendererRegistrationError("renderer revision must be a non-empty string")
        spec = RendererSpec(renderer_id, function, resolved_revision.strip())
        self._specs[renderer_id] = spec
        return spec

    def get(self, renderer_id: str) -> RendererSpec:
        try:
            return self._specs[renderer_id]
        except KeyError as exc:
            raise RendererRegistrationError(f"unknown renderer: {renderer_id}") from exc

    @property
    def specs(self) -> tuple[RendererSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))


def _render_nested(lines: list[str], key: str, value: Any, *, level: int) -> None:
    heading = "#" * min(max(level, 2), 6)
    label = _label(key)
    value = thaw(value)
    if isinstance(value, Mapping):
        lines.extend([f"{heading} {label}", ""])
        if not value:
            lines.extend(["_Empty._", ""])
            return
        for child in sorted(value):
            _render_nested(lines, str(child), value[child], level=level + 1)
        return
    if isinstance(value, (list, tuple)):
        lines.extend([f"{heading} {label}", ""])
        if not value:
            lines.extend(["_None._", ""])
            return
        if all(not isinstance(item, (Mapping, list, tuple)) for item in value):
            lines.extend([f"- {_scalar(item)}" for item in value])
            lines.append("")
            return
        for index, item in enumerate(value, 1):
            if isinstance(item, Mapping):
                lines.append(f"{heading}# Item {index}")
                lines.append("")
                for child in sorted(item):
                    _render_nested(lines, str(child), item[child], level=level + 2)
            else:
                lines.extend(["```json", json.dumps(thaw(item), ensure_ascii=False, sort_keys=True, indent=2), "```", ""])
        return
    if isinstance(value, str) and "\n" in value:
        lines.extend([f"{heading} {label}", "", _normalize_text(value).rstrip("\n"), ""])
        return
    lines.extend([f"**{label}:** {_scalar(value)}", ""])


def render_markdown(value: Any, context: RenderContext) -> str:
    """Generic deterministic Markdown view for JSON-compatible documentation data."""

    data = thaw(value)
    fallback = _label(context.resource_id.split(".")[-1])
    title = fallback
    if isinstance(data, Mapping) and isinstance(data.get("title"), str) and data.get("title", "").strip():
        title = data["title"].strip()
    lines = [f"# {title}", ""]
    if isinstance(data, Mapping):
        for key in sorted(data):
            if key == "title":
                continue
            _render_nested(lines, str(key), data[key], level=2)
    elif isinstance(data, (list, tuple)):
        if not data:
            lines.extend(["_None._", ""])
        elif all(not isinstance(item, (Mapping, list, tuple)) for item in data):
            lines.extend([f"- {_scalar(item)}" for item in data])
            lines.append("")
        else:
            lines.extend(["```json", json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2), "```", ""])
    else:
        lines.extend([_scalar(data), ""])
    return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True, slots=True)
class MaterializationOwner:
    owner: ManagedResource
    target: MaterializationTarget

    @property
    def owner_ref(self) -> ResourceRef:
        return self.owner.raw.ref


class MaterializationStateStore:
    """Machine-owned generated-view digest/provenance state."""

    def __init__(self, roots: ProjectRoots) -> None:
        dep = confined_path(roots.documentation_root, roots.config.dependency_dir)
        raw = roots.documentation_root
        for part in Path(roots.config.dependency_dir).parts:
            raw = raw / part
            if raw.is_symlink():
                raise MaterializationError("dependency runtime path must not contain symlinks")
        state_dir = raw / "state"
        if state_dir.is_symlink():
            raise MaterializationError("materialization state directory must not be a symlink")
        self.path = state_dir / "materialization_state.json"
        docs = roots.documentation_root.resolve(strict=False)
        if not is_within(self.path.resolve(strict=False), docs):
            raise MaterializationError("materialization state escapes documentation root")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
                "state_revision": 0,
                "generated_at": None,
                "outputs": {},
            }
        if self.path.is_symlink():
            raise MaterializationError("materialization_state.json must not be a symlink")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MaterializationError(f"invalid materialization state JSON: {exc}") from exc
        required_top = {"state_schema_version", "state_revision", "generated_at", "outputs"}
        if not isinstance(data, dict) or set(data) != required_top:
            raise MaterializationError("invalid materialization state object")
        if data.get("state_schema_version") != PERSISTED_STATE_SCHEMA_VERSION:
            raise MaterializationError("invalid or unsupported materialization state schema")
        generated_at = data.get("generated_at")
        if generated_at is not None:
            if not isinstance(generated_at, str) or not generated_at:
                raise MaterializationError("materialization generated_at must be string/null")
            try:
                parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise MaterializationError("materialization generated_at must be ISO-8601") from exc
            if parsed.tzinfo is None:
                raise MaterializationError("materialization generated_at must include timezone")
        revision = data.get("state_revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise MaterializationError("materialization state_revision must be a non-negative integer")
        outputs = data.get("outputs")
        if not isinstance(outputs, dict):
            raise MaterializationError("materialization outputs must be an object")
        required = {"owner_ref", "renderer", "renderer_revision", "input_revision", "output_digest", "resource_kind"}
        allowed = required | {"orphan_acknowledged"}
        for path, record in outputs.items():
            if not isinstance(path, str) or not path or not isinstance(record, dict):
                raise MaterializationError("invalid materialization output entry")
            if "\\" in path:
                raise MaterializationError(f"materialization state path must use '/' separators: {path!r}")
            posix = PurePosixPath(path)
            if posix.is_absolute() or any(part in {".", "..", ""} for part in posix.parts) or posix.as_posix() != path:
                raise MaterializationError(f"invalid canonical materialization state path: {path!r}")
            if not required.issubset(record) or not set(record).issubset(allowed) or not all(isinstance(record[k], str) and record[k] for k in required):
                raise MaterializationError(f"invalid materialization record for {path}")
            if "orphan_acknowledged" in record and not isinstance(record["orphan_acknowledged"], bool):
                raise MaterializationError(f"invalid orphan_acknowledged flag for {path}")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", record["output_digest"]):
                raise MaterializationError(f"invalid output digest for {path}")
            if record["resource_kind"] not in {"managed", "derived"}:
                raise MaterializationError(f"invalid resource_kind for {path}: {record['resource_kind']!r}")
            try:
                ref = ResourceRef.parse(record["owner_ref"])
            except RefError as exc:
                raise MaterializationError(f"invalid owner_ref for {path}: {exc}") from exc
            if ref.pointer_parts:
                raise MaterializationError(f"materialization owner must be whole resource: {path}")
        return data

    def write_outputs(self, outputs: Mapping[str, Mapping[str, str]]) -> tuple[dict[str, Any], bool]:
        current = self.load()
        normalized = {key: dict(outputs[key]) for key in sorted(outputs)}
        if current.get("outputs", {}) == normalized:
            return current, False
        payload = {
            "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
            "state_revision": current.get("state_revision", 0) + 1,
            "generated_at": _utc_now(),
            "outputs": normalized,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise MaterializationError("refusing to write materialization state through symlink")
        try:
            _hardened_atomic_write_text(
                self.path,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            )
        except HardeningError as exc:
            raise MaterializationError(str(exc)) from exc
        return payload, True


class MaterializationRuntime:
    def __init__(
        self,
        roots: ProjectRoots,
        catalog: ResourceCatalog,
        builders: BuilderRegistry,
        renderers: RendererRegistry,
        dependency_runtime: DependencyRuntime,
    ) -> None:
        self.roots = roots
        self.catalog = catalog
        self.builders = builders
        self.renderers = renderers
        self.dependency_runtime = dependency_runtime
        self.state = MaterializationStateStore(roots)
        self._owners = tuple(
            MaterializationOwner(resource, target)
            for resource in catalog.managed
            for target in resource.targets
        )
        self._by_path = {item.target.path: item for item in self._owners}
        self._by_owner: dict[str, list[MaterializationOwner]] = {}
        for item in self._owners:
            self._by_owner.setdefault(str(item.owner_ref), []).append(item)

    @property
    def owners(self) -> tuple[MaterializationOwner, ...]:
        return tuple(sorted(self._owners, key=lambda item: (str(item.owner_ref), item.target.path)))

    def _safe_output_path(self, relative: str) -> Path:
        try:
            candidate = confined_path(self.roots.documentation_root, relative)
        except RootDiscoveryError as exc:
            raise MaterializationError(str(exc)) from exc
        raw = self.roots.documentation_root
        for part in Path(relative).parts:
            raw = raw / part
            if raw.is_symlink():
                raise MaterializationError(f"materialization path contains symlink: {relative}")
        if candidate.exists() and not candidate.is_file():
            raise MaterializationError(f"materialization target is not a regular file: {relative}")
        return candidate

    def _validate_derived_evidence(self, owner_ref: ResourceRef, obj: DerivedObject) -> None:
        owner_s = str(owner_ref)
        active = self.dependency_runtime.active_receipts()
        receipt = active.get(owner_s)
        if receipt is None:
            raise MaterializationError(
                f"derived materialization requires a recorded build receipt before rendering: {owner_ref}"
            )
        if not receipt.audit_complete:
            raise MaterializationError(f"derived materialization receipt is audit-incomplete: {owner_ref}")
        state_entry = self.dependency_runtime.status().get("targets", {}).get(owner_s)
        if state_entry is not None and state_entry.get("status") != "valid":
            raise MaterializationError(
                f"derived materialization requires valid dependency state for {owner_ref}; "
                f"current status is {state_entry.get('status')!r}"
            )
        diff = self.dependency_runtime.diff(owner_ref)
        if diff.get("changed"):
            raise MaterializationError(
                f"derived materialization requires rebuild/check before rendering changed target: {owner_ref}"
            )
        if receipt.output_digest and obj.provenance.output_digest != receipt.output_digest:
            raise MaterializationError(
                f"derived materialization output differs from recorded receipt for {owner_ref}; rebuild required"
            )

    def _resolve_input(self, item: MaterializationOwner, cache: dict[str, RawObject | DerivedObject]) -> tuple[Any, str, str]:
        owner_ref = item.owner_ref
        owner_s = str(owner_ref)
        if owner_s in cache:
            obj = cache[owner_s]
        elif self.builders.has_target(owner_ref):
            try:
                obj = BuildEngine(self.catalog, self.builders).build(owner_ref)
            except BuilderError as exc:
                raise MaterializationError(f"cannot build materialization owner {owner_ref}: {exc}") from exc
            cache[owner_s] = obj
        else:
            resolved = self.catalog.resolve(owner_ref)
            if not isinstance(resolved, RawObject):
                raise MaterializationError(f"materialization owner did not resolve to RawObject: {owner_ref}")
            obj = resolved
            cache[owner_s] = obj
        if isinstance(obj, DerivedObject):
            self._validate_derived_evidence(owner_ref, obj)
            return obj.data, obj.version, "derived"
        return obj.data, self.catalog.version(owner_ref), "managed"

    def _record_for(self, item: MaterializationOwner, *, input_revision: str, output_digest: str) -> dict[str, str]:
        renderer = self.renderers.get(item.target.renderer)
        return {
            "owner_ref": str(item.owner_ref),
            "renderer": renderer.renderer_id,
            "renderer_revision": renderer.revision,
            "input_revision": input_revision,
            "output_digest": output_digest,
            "resource_kind": item.owner.kind,
        }

    def _render(self, item: MaterializationOwner, value: Any) -> bytes:
        spec = self.renderers.get(item.target.renderer)
        context = RenderContext(
            owner_ref=item.owner_ref,
            resource_id=item.owner.resource_id,
            resource_kind=item.owner.kind,
            target_path=item.target.path,
            renderer_id=spec.renderer_id,
        )
        try:
            rendered = spec.function(value, context)
        except MaterializationError:
            raise
        except SystemExit as exc:
            raise RendererExecutionError(
                f"renderer {spec.renderer_id!r} exited for {item.owner_ref} -> {item.target.path}: {exc}"
            ) from exc
        except Exception as exc:
            raise RendererExecutionError(
                f"renderer {spec.renderer_id!r} failed for {item.owner_ref} -> {item.target.path}: {exc}"
            ) from exc
        if isinstance(rendered, str):
            return _normalize_text(rendered).encode("utf-8")
        if isinstance(rendered, bytes):
            return rendered
        raise RendererExecutionError(
            f"renderer {spec.renderer_id!r} returned unsupported {type(rendered).__name__}; expected str or bytes"
        )

    def select(self, target: ResourceRef | str | None = None, *, all_targets: bool = False) -> tuple[MaterializationOwner, ...]:
        if all_targets:
            if target is not None:
                raise MaterializationError("materialize target and --all are mutually exclusive")
            return self.owners
        if target is None:
            raise MaterializationError("materialize requires TARGET or --all")
        ref = ResourceRef.parse(target) if isinstance(target, str) else target
        if ref.scheme == "file":
            assert ref.file_path is not None
            try:
                return (self._by_path[ref.file_path],)
            except KeyError as exc:
                raise MaterializationError(f"file is not a registered materialization target: {ref}") from exc
        if ref.scheme == "resource":
            if ref.pointer_parts:
                raise MaterializationError("materialization target must be a whole resource or generated file")
            items = tuple(sorted(self._by_owner.get(str(ref), ()), key=lambda item: item.target.path))
            if not items:
                raise MaterializationError(f"resource has no registered materialization target: {ref}")
            return items
        raise MaterializationError(f"unsupported materialization target: {ref}")

    def inspect(self, items: Sequence[MaterializationOwner] | None = None) -> dict[str, Any]:
        selected = tuple(items) if items is not None else self.owners
        state = self.state.load()
        records = state.get("outputs", {})
        cache: dict[str, RawObject | DerivedObject] = {}
        results: list[dict[str, Any]] = []
        for item in selected:
            record = records.get(item.target.path)
            row: dict[str, Any] = {
                "path": item.target.path,
                "owner_ref": str(item.owner_ref),
                "renderer": item.target.renderer,
                "registered": True,
                "state": "current",
                "drift": False,
                "outdated": False,
                "needs_materialization": False,
            }
            try:
                path = self._safe_output_path(item.target.path)
                value, input_revision, _ = self._resolve_input(item, cache)
                renderer = self.renderers.get(item.target.renderer)
                row["input_revision"] = input_revision
                row["renderer_revision"] = renderer.revision
                if record is None:
                    row.update(state="unmaterialized", needs_materialization=True)
                else:
                    if (
                        record.get("owner_ref") != str(item.owner_ref)
                        or record.get("renderer") != renderer.renderer_id
                        or record.get("renderer_revision") != renderer.revision
                        or record.get("input_revision") != input_revision
                        or record.get("resource_kind") != item.owner.kind
                    ):
                        row.update(state="outdated", outdated=True, needs_materialization=True)
                    if not path.exists():
                        row.update(state="missing", drift=True, needs_materialization=True, current_digest=None)
                    else:
                        current_digest = _sha256(path.read_bytes())
                        row["current_digest"] = current_digest
                        row["expected_digest"] = record.get("output_digest")
                        if current_digest != record.get("output_digest"):
                            row.update(state="drifted", drift=True, needs_materialization=True)
                # Keep value resolution intentional: this is a current-input probe,
                # not a render/write. ``value`` is unused after proving availability.
                del value
            except (MaterializationError, RendererRegistrationError, ResourceError, BuilderError, RefError) as exc:
                row.update(state="error", needs_materialization=False, error=str(exc))
            results.append(row)
        registered_paths = {item.target.path for item in self._owners}
        orphans = [
            {
                "path": path,
                "record": records[path],
                "state": "orphaned_state",
                "acknowledged": bool(records[path].get("orphan_acknowledged", False)),
            }
            for path in sorted(set(records) - registered_paths)
        ]
        return {
            "outputs": results,
            "orphans": orphans,
            "unresolved_orphans": sum(1 for item in orphans if not item["acknowledged"]),
            "drifted": sum(1 for row in results if row.get("drift")),
            "outdated": sum(1 for row in results if row.get("outdated")),
            "needs_materialization": sum(1 for row in results if row.get("needs_materialization")),
            "errors": sum(1 for row in results if row.get("state") == "error"),
        }

    def materialize_items(
        self,
        items: Sequence[MaterializationOwner],
        *,
        object_cache: Mapping[str, RawObject | DerivedObject] | None = None,
    ) -> dict[str, Any]:
        cache: dict[str, RawObject | DerivedObject] = dict(object_cache or {})
        state = self.state.load()
        outputs = dict(state.get("outputs", {}))
        prepared: list[tuple[MaterializationOwner, Path, bytes, dict[str, str], str | None]] = []
        for item in items:
            path = self._safe_output_path(item.target.path)
            value, input_revision, _ = self._resolve_input(item, cache)
            rendered = self._render(item, value)
            digest = _sha256(rendered)
            record = self._record_for(item, input_revision=input_revision, output_digest=digest)
            current_digest = _sha256(path.read_bytes()) if path.is_file() else None
            prepared.append((item, path, rendered, record, current_digest))

        results: list[dict[str, Any]] = []
        updates = dict(outputs)
        for item, path, rendered, record, current_digest in prepared:
            written = current_digest != record["output_digest"]
            if written:
                path.parent.mkdir(parents=True, exist_ok=True)
                # Parent creation may expose a pre-existing symlink only after mkdir
                # races; re-check the lexical path immediately before replacement.
                self._safe_output_path(item.target.path)
                try:
                    _hardened_atomic_write_bytes(path, rendered)
                except HardeningError as exc:
                    raise MaterializationError(str(exc)) from exc
            state_record_changed = updates.get(item.target.path) != record
            updates[item.target.path] = record
            results.append({
                "path": item.target.path,
                "owner_ref": str(item.owner_ref),
                "renderer": item.target.renderer,
                "output_digest": record["output_digest"],
                "input_revision": record["input_revision"],
                "written": written,
                "state_record_changed": state_record_changed,
            })
        state_payload, state_changed = self.state.write_outputs(updates)
        return {
            "results": results,
            "written": sum(1 for row in results if row["written"]),
            "state_changed": state_changed,
            "state_revision": state_payload.get("state_revision", 0),
        }

    def acknowledge_orphan(self, target: ResourceRef | str) -> dict[str, Any]:
        ref = ResourceRef.parse(target) if isinstance(target, str) else target
        if ref.scheme != "file" or ref.file_path is None:
            raise MaterializationError("orphan acknowledgement requires a whole file:// target")
        path = ref.file_path
        if path in self._by_path:
            raise MaterializationError(f"cannot acknowledge currently registered materialization target: {ref}")
        state = self.state.load()
        outputs = dict(state.get("outputs", {}))
        if path not in outputs:
            raise MaterializationError(f"no orphaned materialization state for: {ref}")
        previous = dict(outputs[path])
        already_acknowledged = bool(previous.get("orphan_acknowledged", False))
        previous["orphan_acknowledged"] = True
        outputs[path] = previous
        payload, changed = self.state.write_outputs(outputs)
        return {
            "path": path,
            "owner_ref": previous.get("owner_ref"),
            "state_changed": changed,
            "state_revision": payload.get("state_revision", 0),
            "file_preserved": True,
            "already_acknowledged": already_acknowledged,
        }

    def materialize(self, target: ResourceRef | str | None = None, *, all_targets: bool = False) -> dict[str, Any]:
        selected = self.select(target, all_targets=all_targets)
        before = self.inspect(selected)
        result = self.materialize_items(selected)
        after = self.inspect(selected)
        return {"selection_count": len(selected), "before": before, **result, "after": after}


@dataclass(frozen=True, slots=True)
class CombinedSCC:
    members: tuple[str, ...]
    builder_members: tuple[str, ...]
    semantic_members: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "members": list(self.members),
            "builder_members": list(self.builder_members),
            "semantic_members": list(self.semantic_members),
            "kind": "mixed" if self.builder_members and self.semantic_members else "deterministic",
        }


class SyncRuntime:
    """Bounded P5 orchestration over P2 builders, P3 state and P4 review rules."""

    def __init__(
        self,
        dependency_runtime: DependencyRuntime,
        semantic_registry: SemanticDependencyRegistry,
        materialization_runtime: MaterializationRuntime,
    ) -> None:
        self.runtime = dependency_runtime
        self.semantic_registry = semantic_registry
        self.materialization = materialization_runtime
        self.builders = materialization_runtime.builders

    @staticmethod
    def _node(ref: ResourceRef | str) -> str:
        parsed = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if parsed.scheme == "resource" and parsed.pointer_parts:
            parsed = ResourceRef(
                scheme="resource",
                namespace=parsed.namespace,
                resource_id=parsed.resource_id,
                pointer_parts=(),
            )
        return str(parsed)

    def _combined_sccs(self) -> tuple[CombinedSCC, ...]:
        active = self.runtime.active_receipts()
        builder_nodes = {str(spec.target) for spec in self.builders.specs}
        semantic_nodes = {self._node(rule.target) for rule in self.semantic_registry.rules}
        nodes = builder_nodes | semantic_nodes
        edges: dict[str, set[str]] = {node: set() for node in nodes}
        for target, receipt in active.items():
            target_node = self._node(target)
            if target_node not in builder_nodes:
                continue
            for dep in receipt.dependencies:
                source_node = self._node(dep.source)
                if source_node in nodes:
                    edges.setdefault(target_node, set()).add(source_node)
        for rule in self.semantic_registry.rules:
            target_node = self._node(rule.target)
            for dep in rule.dependencies:
                source_node = self._node(dep.source)
                if source_node in nodes:
                    edges.setdefault(target_node, set()).add(source_node)

        index = 0
        indices: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        components: list[tuple[str, ...]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for nxt in sorted(edges.get(node, ())):
                if nxt not in indices:
                    visit(nxt)
                    lowlink[node] = min(lowlink[node], lowlink[nxt])
                elif nxt in on_stack:
                    lowlink[node] = min(lowlink[node], indices[nxt])
            if lowlink[node] == indices[node]:
                component: list[str] = []
                while True:
                    current = stack.pop()
                    on_stack.remove(current)
                    component.append(current)
                    if current == node:
                        break
                components.append(tuple(sorted(component)))

        for node in sorted(nodes):
            if node not in indices:
                visit(node)

        result: list[CombinedSCC] = []
        for members in components:
            self_loop = len(members) == 1 and members[0] in edges.get(members[0], set())
            if len(members) < 2 and not self_loop:
                continue
            builders = tuple(sorted(set(members) & builder_nodes))
            semantics = tuple(sorted(set(members) & semantic_nodes))
            result.append(CombinedSCC(members, builders, semantics))
        return tuple(sorted(result, key=lambda item: item.members))

    def rebuild(self, target: ResourceRef | str) -> dict[str, Any]:
        ref = ResourceRef.parse(target) if isinstance(target, str) else target
        if not self.builders.has_target(ref):
            raise MaterializationError(f"no deterministic builder registered for {ref}")
        try:
            result = BuildEngine(self.materialization.catalog, self.builders).build(ref)
        except BuilderError as exc:
            raise MaterializationError(f"deterministic rebuild failed for {ref}: {exc}") from exc
        receipt = self.runtime.record_build(result)
        status = self.runtime.status().get("targets", {}).get(str(ref), {}).get("status")
        return {
            "target": str(ref),
            "receipt_id": receipt.receipt_id,
            "output_digest": result.provenance.output_digest,
            "audit_complete": receipt.audit_complete,
            "status": status,
            "object": result,
        }

    def sync(self, *, all_targets: bool = False) -> dict[str, Any]:
        initial_check = (
            SemanticReviewRuntime(self.runtime, self.semantic_registry).check_all()
            if self.semantic_registry.rules
            else self.runtime.check_all()
        )
        initial_state = self.runtime.status().get("targets", {})
        active = self.runtime.active_receipts()

        sccs_before = self._combined_sccs()
        deterministic_cycles = [scc for scc in sccs_before if scc.builder_members and not scc.semantic_members]
        if deterministic_cycles:
            raise MaterializationError(
                "deterministic dependency cycle detected during sync planning: "
                + "; ".join(" -> ".join(scc.members) for scc in deterministic_cycles)
            )

        candidates: list[str] = []
        for spec in self.builders.specs:
            target = str(spec.target)
            state = initial_state.get(target)
            if target not in active or (state and state.get("status") == "build_required"):
                candidates.append(target)

        rebuilt: list[dict[str, Any]] = []
        object_cache: dict[str, RawObject | DerivedObject] = {}
        attempted: set[str] = set()
        for target in sorted(candidates):
            if target in attempted:
                continue
            attempted.add(target)
            info = self.rebuild(target)
            obj = info.pop("object")
            object_cache[target] = obj
            rebuilt.append(info)

        final_check = (
            SemanticReviewRuntime(self.runtime, self.semantic_registry).check_all()
            if self.semantic_registry.rules
            else self.runtime.check_all()
        )
        final_state = self.runtime.status().get("targets", {})
        final_results = {item["target"]: item for item in final_check.get("results", [])}
        attention_targets = sorted(
            target for target, item in final_results.items()
            if item.get("status") in {"review_required", "stale"}
        )
        invalid_targets = sorted(
            target for target, item in final_results.items() if item.get("status") == "invalid"
        )
        unresolved_builds = sorted(
            target for target, item in final_results.items() if item.get("status") == "build_required"
        )
        attention_targets = sorted(set(attention_targets) | {
            target for target, entry in final_state.items()
            if entry.get("status") in {"review_required", "stale"}
        })
        invalid_targets = sorted(set(invalid_targets) | {
            target for target, entry in final_state.items() if entry.get("status") == "invalid"
        })
        unresolved_builds = sorted(set(unresolved_builds) | {
            target for target, entry in final_state.items() if entry.get("status") == "build_required"
        })

        sccs_after = self._combined_sccs()
        mixed_sccs = [scc for scc in sccs_after if scc.builder_members and scc.semantic_members]
        affected_nodes = {self._node(target) for target in attempted}
        affected_nodes.update(self._node(target) for target, entry in final_state.items() if entry.get("status") in {"review_required", "stale"})
        attention_mixed = [scc for scc in mixed_sccs if set(scc.members) & affected_nodes]

        if invalid_targets or unresolved_builds:
            return {
                "ok": False,
                "status": "sync_failed",
                "initial_check": initial_check,
                "final_check": final_check,
                "rebuilt": rebuilt,
                "materialization": {
                    "results": [],
                    "written": 0,
                    "state_changed": False,
                    "state_revision": self.materialization.state.load().get("state_revision", 0),
                    "skipped": "invalid_or_build_required_targets",
                },
                "attention_targets": attention_targets,
                "invalid_targets": invalid_targets,
                "unresolved_builds": unresolved_builds,
                "mixed_sccs": [scc.to_dict() for scc in attention_mixed],
                "orphaned_materializations": [],
            }

        inspection = self.materialization.inspect()
        if inspection["errors"]:
            errors = [row for row in inspection["outputs"] if row.get("state") == "error"]
            raise MaterializationError(f"cannot inspect materialization targets: {errors}")
        if all_targets:
            selected = self.materialization.owners
        else:
            affected_paths = {
                row["path"] for row in inspection["outputs"] if row.get("needs_materialization")
            }
            selected = tuple(item for item in self.materialization.owners if item.target.path in affected_paths)
        materialized = self.materialization.materialize_items(selected, object_cache=object_cache) if selected else {
            "results": [], "written": 0, "state_changed": False,
            "state_revision": self.materialization.state.load().get("state_revision", 0),
        }

        all_orphans = inspection.get("orphans", [])
        orphaned_materializations = [item for item in all_orphans if not item.get("acknowledged")]
        acknowledged_orphans = [item for item in all_orphans if item.get("acknowledged")]
        status = "attention_required" if attention_targets or attention_mixed or orphaned_materializations else "ok"
        return {
            "ok": True,
            "status": status,
            "initial_check": initial_check,
            "final_check": final_check,
            "rebuilt": rebuilt,
            "materialization": materialized,
            "attention_targets": attention_targets,
            "invalid_targets": [],
            "unresolved_builds": [],
            "mixed_sccs": [scc.to_dict() for scc in attention_mixed],
            "orphaned_materializations": orphaned_materializations,
            "acknowledged_orphaned_materializations": acknowledged_orphans,
        }


__all__ = [
    "CombinedSCC",
    "MaterializationError",
    "MaterializationOwner",
    "MaterializationRuntime",
    "MaterializationStateStore",
    "RenderContext",
    "RendererExecutionError",
    "RendererRegistry",
    "RendererRegistrationError",
    "RendererSpec",
    "SyncRuntime",
    "render_markdown",
]
