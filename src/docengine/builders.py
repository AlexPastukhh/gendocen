"""Domain-neutral builder runtime with dependency-aware tracked reads."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Protocol

from .objects import FrozenMapping, RawObject, freeze, resolve_pointer, thaw
from .refs import RefError, ResourceRef


class BuilderError(RuntimeError):
    """Base class for builder/runtime failures."""


class BuilderRegistrationError(BuilderError):
    pass


class BuilderNotFoundError(BuilderError):
    pass


class BuildCycleError(BuilderError):
    def __init__(self, cycle: tuple[str, ...]):
        self.cycle = cycle
        super().__init__("dependency cycle detected: " + " -> ".join(cycle))


class BuilderExecutionError(BuilderError):
    pass


class BuildStore(Protocol):
    def get(self, ref: ResourceRef | str) -> Any: ...
    def version(self, ref: ResourceRef | str) -> str: ...


BuilderFunction = Callable[["BuildContext"], Any]

_ALLOWED_BUILDER_DEPENDENCY_TYPES = frozenset({"copy_reference", "compute", "aggregate"})


def _whole_resource_ref(ref: ResourceRef) -> ResourceRef:
    if ref.scheme != "resource":
        raise BuilderError("builders may target only structured resource refs")
    return ResourceRef(
        scheme="resource",
        namespace=ref.namespace,
        resource_id=ref.resource_id,
        pointer_parts=(),
    )




def _validate_derived_value(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BuilderExecutionError(f"derived data contains non-finite number at {path}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise BuilderExecutionError(f"derived object keys must be strings at {path}")
            _validate_derived_value(item, path=f"{path}/{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_derived_value(item, path=f"{path}/{index}")
        return
    if isinstance(value, FrozenMapping):
        for key, item in value.items():
            _validate_derived_value(item, path=f"{path}/{key}")
        return
    raise BuilderExecutionError(f"derived data is not JSON-compatible at {path}: {type(value).__name__}")

def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _value_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class BuilderSpec:
    builder_id: str
    target: ResourceRef
    function: BuilderFunction
    dependency_type: str = "compute"
    comparator: str = "exact"
    source_revision: str = "unversioned"

    def to_dict(self) -> dict[str, str]:
        return {
            "builder_id": self.builder_id,
            "target": str(self.target),
            "dependency_type": self.dependency_type,
            "comparator": self.comparator,
            "source_revision": self.source_revision,
        }


class BuilderRegistry:
    """Canonical explicit registry. ``builder()`` is decorator convenience only.

    ``source_revision`` identifies the code bundle that registered builders. Project
    extension loading supplies a content digest; direct/in-memory callers may leave
    the explicit ``unversioned`` marker for synthetic/test use.
    """

    def __init__(self, *, source_revision: str = "unversioned") -> None:
        if not isinstance(source_revision, str) or not source_revision.strip():
            raise BuilderRegistrationError("source_revision must be a non-empty string")
        self.source_revision = source_revision.strip()
        self._by_target: dict[str, BuilderSpec] = {}
        self._by_id: dict[str, BuilderSpec] = {}

    @staticmethod
    def _parse_target(target: ResourceRef | str) -> ResourceRef:
        try:
            ref = ResourceRef.parse(target) if isinstance(target, str) else target
        except RefError as exc:
            raise BuilderRegistrationError(str(exc)) from exc
        if ref.scheme != "resource" or ref.pointer_parts:
            raise BuilderRegistrationError("builder target must be a whole structured resource ref")
        return ref

    def register(
        self,
        target: ResourceRef | str,
        function: BuilderFunction,
        *,
        builder_id: str | None = None,
        dependency_type: str = "compute",
        comparator: str = "exact",
    ) -> BuilderSpec:
        ref = self._parse_target(target)
        if not callable(function):
            raise BuilderRegistrationError("builder function must be callable")
        if dependency_type not in _ALLOWED_BUILDER_DEPENDENCY_TYPES:
            raise BuilderRegistrationError(
                f"builder dependency_type must be one of {sorted(_ALLOWED_BUILDER_DEPENDENCY_TYPES)}"
            )
        if not isinstance(comparator, str) or not comparator:
            raise BuilderRegistrationError("builder comparator must be a non-empty string")
        logical_id = ref.logical_resource_id
        assert logical_id is not None
        resolved_id = builder_id or f"build:{logical_id}"
        if not isinstance(resolved_id, str) or not resolved_id:
            raise BuilderRegistrationError("builder_id must be a non-empty string")
        if logical_id in self._by_target:
            raise BuilderRegistrationError(f"builder already registered for target {ref}")
        if resolved_id in self._by_id:
            raise BuilderRegistrationError(f"duplicate builder_id: {resolved_id}")
        spec = BuilderSpec(
            builder_id=resolved_id,
            target=ref,
            function=function,
            dependency_type=dependency_type,
            comparator=comparator,
            source_revision=self.source_revision,
        )
        self._by_target[logical_id] = spec
        self._by_id[resolved_id] = spec
        return spec

    def builder(
        self,
        target: ResourceRef | str,
        *,
        builder_id: str | None = None,
        dependency_type: str = "compute",
        comparator: str = "exact",
    ) -> Callable[[BuilderFunction], BuilderFunction]:
        def decorate(function: BuilderFunction) -> BuilderFunction:
            self.register(
                target,
                function,
                builder_id=builder_id,
                dependency_type=dependency_type,
                comparator=comparator,
            )
            return function
        return decorate

    def has_target(self, target: ResourceRef | str) -> bool:
        try:
            ref = self._parse_target(target)
        except BuilderRegistrationError:
            return False
        logical_id = ref.logical_resource_id
        assert logical_id is not None
        return logical_id in self._by_target

    def get(self, target: ResourceRef | str) -> BuilderSpec:
        ref = self._parse_target(target)
        logical_id = ref.logical_resource_id
        assert logical_id is not None
        try:
            return self._by_target[logical_id]
        except KeyError as exc:
            raise BuilderNotFoundError(f"no builder registered for {ref}") from exc

    @property
    def specs(self) -> tuple[BuilderSpec, ...]:
        return tuple(self._by_target[key] for key in sorted(self._by_target))


@dataclass(frozen=True, slots=True)
class DependencyRead:
    ref: ResourceRef
    version: str
    source_kind: str
    comparator: str
    snapshot_value: Any
    source_audit_complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": str(self.ref),
            "version": self.version,
            "source_kind": self.source_kind,
            "comparator": self.comparator,
            "snapshot_digest": _value_digest(self.snapshot_value),
            "source_audit_complete": self.source_audit_complete,
        }


@dataclass(frozen=True, slots=True)
class UntrackedAccess:
    ref: ResourceRef
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"ref": str(self.ref), "reason": self.reason}


@dataclass(frozen=True, slots=True)
class BuildProvenance:
    builder_id: str
    builder_revision: str
    target: ResourceRef
    dependency_type: str
    comparator: str
    tracking_assurance: str
    dependencies: tuple[DependencyRead, ...]
    untracked_accesses: tuple[UntrackedAccess, ...]
    output_digest: str
    provenance_digest: str

    @property
    def audit_complete(self) -> bool:
        return not self.untracked_accesses and all(item.source_audit_complete for item in self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "builder_id": self.builder_id,
            "builder_revision": self.builder_revision,
            "target": str(self.target),
            "dependency_type": self.dependency_type,
            "comparator": self.comparator,
            "tracking_assurance": self.tracking_assurance,
            "dependencies": [item.to_dict() for item in self.dependencies],
            "untracked_accesses": [item.to_dict() for item in self.untracked_accesses],
            "audit_complete": self.audit_complete,
            "output_digest": self.output_digest,
            "provenance_digest": self.provenance_digest,
        }


@dataclass(frozen=True, slots=True)
class DerivedObject:
    resource_id: str
    ref: ResourceRef
    data: FrozenMapping | tuple[Any, ...]
    provenance: BuildProvenance

    def read(self, ref: ResourceRef | str) -> Any:
        field_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if field_ref.scheme != "resource" or field_ref.logical_resource_id != self.resource_id:
            raise KeyError(f"reference does not address {self.resource_id}")
        return resolve_pointer(self.data, field_ref.pointer_parts)

    @property
    def version(self) -> str:
        return self.provenance.output_digest

    def version_for(self, ref: ResourceRef) -> str:
        if ref.logical_resource_id != self.resource_id:
            raise KeyError(f"reference does not address {self.resource_id}")
        if not ref.pointer_parts:
            return self.version
        return _value_digest(self.read(ref))

    def to_builtin(self) -> Any:
        return thaw(self.data)

    def to_envelope(self) -> dict[str, Any]:
        return {
            "$docengine": {
                "resource_id": self.resource_id,
                "resource_kind": "derived",
                "provenance": self.provenance.to_dict(),
            },
            "data": self.to_builtin(),
        }


class BuildContext:
    """Context passed to project builders.

    ``read`` tracks the exact supplied field/resource/file ref.
    ``get`` tracks a whole resource and returns its object wrapper.
    ``untracked_read`` is an explicit escape hatch and marks provenance incomplete.
    """

    def __init__(self, session: "_BuildSession", target: ResourceRef, *, default_comparator: str):
        self._session = session
        self.target = target
        self._default_comparator = default_comparator
        self._dependencies: dict[str, DependencyRead] = {}
        self._untracked: list[UntrackedAccess] = []
        self._emitted: Any = _NO_OUTPUT

    def _record(
        self,
        ref: ResourceRef,
        *,
        version: str,
        source_kind: str,
        comparator: str,
        snapshot_value: Any,
        source_audit_complete: bool = True,
    ) -> None:
        key = str(ref)
        existing = self._dependencies.get(key)
        item = DependencyRead(
            ref=ref,
            version=version,
            source_kind=source_kind,
            comparator=comparator,
            snapshot_value=freeze(snapshot_value),
            source_audit_complete=source_audit_complete,
        )
        if existing is not None and existing != item:
            raise BuilderExecutionError(f"dependency evidence changed during one build: {ref}")
        self._dependencies[key] = item

    def read(self, ref: ResourceRef | str, *, comparator: str | None = None) -> Any:
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        selected_comparator = self._default_comparator if comparator is None else comparator
        if not isinstance(selected_comparator, str) or not selected_comparator.strip():
            raise BuilderExecutionError("dependency comparator must be a non-empty string")
        selected_comparator = selected_comparator.strip()
        value, version, source_kind, source_audit_complete = self._session.resolve_value(resource_ref)
        self._record(
            resource_ref,
            version=version,
            source_kind=source_kind,
            comparator=selected_comparator,
            snapshot_value=value,
            source_audit_complete=source_audit_complete,
        )
        return value

    def get(self, ref: ResourceRef | str, *, comparator: str | None = None) -> RawObject | DerivedObject:
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        selected_comparator = self._default_comparator if comparator is None else comparator
        if not isinstance(selected_comparator, str) or not selected_comparator.strip():
            raise BuilderExecutionError("dependency comparator must be a non-empty string")
        selected_comparator = selected_comparator.strip()
        if resource_ref.scheme != "resource" or resource_ref.pointer_parts:
            raise BuilderExecutionError("BuildContext.get requires a whole structured resource ref")
        value, version, source_kind, source_audit_complete = self._session.resolve_object(resource_ref)
        self._record(
            resource_ref,
            version=version,
            source_kind=source_kind,
            comparator=selected_comparator,
            snapshot_value=value.data,
            source_audit_complete=source_audit_complete,
        )
        return value

    def untracked_read(self, ref: ResourceRef | str, *, reason: str) -> Any:
        if not isinstance(reason, str) or not reason.strip():
            raise BuilderExecutionError("untracked_read requires a non-empty reason")
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        value, _, _, _ = self._session.resolve_value(resource_ref)
        self._untracked.append(UntrackedAccess(ref=resource_ref, reason=reason.strip()))
        return value

    def emit(self, value: Any) -> None:
        if self._emitted is not _NO_OUTPUT:
            raise BuilderExecutionError("builder may emit at most one output")
        self._emitted = value

    @property
    def dependency_reads(self) -> tuple[DependencyRead, ...]:
        return tuple(self._dependencies[key] for key in sorted(self._dependencies))

    @property
    def untracked_accesses(self) -> tuple[UntrackedAccess, ...]:
        return tuple(sorted(self._untracked, key=lambda item: (str(item.ref), item.reason)))


_NO_OUTPUT = object()


class _BuildSession:
    def __init__(self, store: BuildStore, registry: BuilderRegistry):
        self.store = store
        self.registry = registry
        self.cache: dict[str, DerivedObject] = {}
        self.stack: list[str] = []

    @staticmethod
    def _whole_ref(ref: ResourceRef) -> ResourceRef:
        return _whole_resource_ref(ref)

    def _is_derived(self, ref: ResourceRef) -> bool:
        return ref.scheme == "resource" and self.registry.has_target(self._whole_ref(ref))

    def resolve_object(self, ref: ResourceRef) -> tuple[RawObject | DerivedObject, str, str, bool]:
        whole = self._whole_ref(ref)
        if self.registry.has_target(whole):
            obj = self.build(whole)
            return obj, obj.version, "derived", obj.provenance.audit_complete
        value = self.store.get(whole)
        if not isinstance(value, RawObject):
            raise BuilderExecutionError(f"store.get({whole}) must return RawObject for whole structured refs")
        return value, self.store.version(whole), "raw", True

    def resolve_value(self, ref: ResourceRef) -> tuple[Any, str, str, bool]:
        if ref.scheme == "resource" and self._is_derived(ref):
            obj = self.build(self._whole_ref(ref))
            value = obj.data if not ref.pointer_parts else obj.read(ref)
            return value, obj.version_for(ref), "derived", obj.provenance.audit_complete
        value = self.store.get(ref)
        version = self.store.version(ref)
        if ref.scheme == "resource" and not ref.pointer_parts and isinstance(value, RawObject):
            value = value.data
        return value, version, "file" if ref.scheme == "file" else "raw", True

    def build(self, target: ResourceRef) -> DerivedObject:
        target = self._whole_ref(target)
        logical_id = target.logical_resource_id
        assert logical_id is not None
        if logical_id in self.cache:
            return self.cache[logical_id]
        if logical_id in self.stack:
            start = self.stack.index(logical_id)
            cycle_ids = self.stack[start:] + [logical_id]
            cycle = tuple(str(ResourceRef.from_resource_id(item)) for item in cycle_ids)
            raise BuildCycleError(cycle)
        spec = self.registry.get(target)
        self.stack.append(logical_id)
        try:
            context = BuildContext(self, target, default_comparator=spec.comparator)
            try:
                returned = spec.function(context)
            except BuildCycleError:
                raise
            except BuilderError:
                raise
            except SystemExit as exc:
                raise BuilderExecutionError(f"builder {spec.builder_id!r} exited for {target}: {exc}") from exc
            except Exception as exc:
                raise BuilderExecutionError(f"builder {spec.builder_id!r} failed for {target}: {exc}") from exc
            if returned is not None and context._emitted is not _NO_OUTPUT:
                raise BuilderExecutionError("builder must either return an output or call ctx.emit(), not both")
            output = context._emitted if context._emitted is not _NO_OUTPUT else returned
            if output is None:
                raise BuilderExecutionError("builder produced no output")
            if not isinstance(output, (Mapping, list, tuple, FrozenMapping)):
                raise BuilderExecutionError("derived object data must be an object or array")
            _validate_derived_value(output)
            frozen = freeze(output)
            if not isinstance(frozen, (FrozenMapping, tuple)):
                raise BuilderExecutionError("derived object data must be an object or array")
            output_digest = _value_digest(frozen)
            dependency_payload = [item.to_dict() for item in context.dependency_reads]
            untracked_payload = [item.to_dict() for item in context.untracked_accesses]
            provenance_base = {
                "builder_id": spec.builder_id,
                "builder_revision": spec.source_revision,
                "target": str(target),
                "dependency_type": spec.dependency_type,
                "comparator": spec.comparator,
                "tracking_assurance": "cooperative",
                "dependencies": dependency_payload,
                "untracked_accesses": untracked_payload,
                "output_digest": output_digest,
            }
            provenance_digest = hashlib.sha256(
                json.dumps(provenance_base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            provenance = BuildProvenance(
                builder_id=spec.builder_id,
                builder_revision=spec.source_revision,
                target=target,
                dependency_type=spec.dependency_type,
                comparator=spec.comparator,
                tracking_assurance="cooperative",
                dependencies=context.dependency_reads,
                untracked_accesses=context.untracked_accesses,
                output_digest=output_digest,
                provenance_digest=provenance_digest,
            )
            result = DerivedObject(
                resource_id=logical_id,
                ref=target,
                data=frozen,
                provenance=provenance,
            )
            self.cache[logical_id] = result
            return result
        finally:
            popped = self.stack.pop()
            assert popped == logical_id


class BuildEngine:
    """Execute registered builders without persisting P3 dependency state."""

    def __init__(self, store: BuildStore, registry: BuilderRegistry):
        self.store = store
        self.registry = registry

    def build(self, target: ResourceRef | str) -> DerivedObject:
        ref = ResourceRef.parse(target) if isinstance(target, str) else target
        if ref.scheme != "resource" or ref.pointer_parts:
            raise BuilderError("build target must be a whole structured resource ref")
        return _BuildSession(self.store, self.registry).build(ref)


__all__ = [
    "BuildContext",
    "BuildCycleError",
    "BuildEngine",
    "BuildProvenance",
    "BuilderError",
    "BuilderExecutionError",
    "BuilderNotFoundError",
    "BuilderRegistry",
    "BuilderRegistrationError",
    "BuilderSpec",
    "DependencyRead",
    "DerivedObject",
    "UntrackedAccess",
]
