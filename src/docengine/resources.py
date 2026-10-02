"""Resource discovery, managed JSON loading, cataloguing and resolution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .jsonio import StrictJsonError, load_strict
from .objects import RawObject, thaw
from .project import ProjectRoots, RootDiscoveryError, confined_path, is_within
from .refs import RefError, ResourceRef
from .schema import ProjectSchemaRegistry, SchemaResolutionError, SchemaValidationError


class ResourceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MaterializationTarget:
    renderer: str
    path: str
    path_base: str = "documentation_root"

    def to_dict(self) -> dict[str, str]:
        return {"renderer": self.renderer, "path": self.path, "path_base": self.path_base}


@dataclass(frozen=True, slots=True)
class ManagedResource:
    raw: RawObject
    source_relative: str
    targets: tuple[MaterializationTarget, ...]
    source_hash: str

    @property
    def resource_id(self) -> str:
        return self.raw.resource_id

    @property
    def kind(self) -> str:
        return "derived" if self.raw.resource_kind == "derived_descriptor" else "managed"

    def to_inventory_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ref": str(self.raw.ref),
            "resource_id": self.resource_id,
            "source": self.source_relative,
            "schema": self.raw.schema_uri,
            "source_hash": self.source_hash,
            "materialize": [target.to_dict() for target in self.targets],
        }


@dataclass(frozen=True, slots=True)
class ResourceInventoryItem:
    kind: str
    ref: str
    source: str | None = None
    resource_id: str | None = None
    owner_ref: str | None = None
    renderer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "kind": self.kind,
            "ref": self.ref,
            "source": self.source,
            "resource_id": self.resource_id,
            "owner_ref": self.owner_ref,
            "renderer": self.renderer,
        }
        return {key: value for key, value in data.items() if value is not None}


def _canonical_value_hash(value: Any) -> str:
    canonical = json.dumps(
        thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = load_strict(path)
    except StrictJsonError as exc:
        raise ResourceError(str(exc)) from exc
    if not isinstance(value, dict):
        raise ResourceError(f"managed resource must be a JSON object: {path}")
    return value


def _validate_envelope(value: dict[str, Any], *, source: Path) -> None:
    if set(value) != {"$docengine", "data"}:
        raise ResourceError(f"{source}: managed resource must contain only '$docengine' and 'data'")
    meta = value["$docengine"]
    if not isinstance(meta, dict):
        raise ResourceError(f"{source}: $docengine must be an object")
    resource_id = meta.get("resource_id")
    if not isinstance(resource_id, str) or not resource_id:
        raise ResourceError(f"{source}: $docengine.resource_id must be a non-empty string")
    try:
        ResourceRef.from_resource_id(resource_id)
    except RefError as exc:
        raise ResourceError(f"{source}: invalid resource_id {resource_id!r}: {exc}") from exc
    if meta.get("resource_kind", "structured") not in {"structured", "derived_descriptor"}:
        raise ResourceError(f"{source}: unsupported resource_kind")
    materialize = meta.get("materialize")
    if not isinstance(materialize, list):
        raise ResourceError(f"{source}: $docengine.materialize must be an array")
    if not isinstance(value["data"], (dict, list)):
        raise ResourceError(f"{source}: data must be object or array")
    if "schema" in meta and (not isinstance(meta["schema"], str) or not meta["schema"]):
        raise ResourceError(f"{source}: $docengine.schema must be a non-empty string")
    for index, target in enumerate(materialize):
        if not isinstance(target, dict):
            raise ResourceError(f"{source}: materialize[{index}] must be an object")


def _target_from_meta(meta: dict[str, Any], *, roots: ProjectRoots, source: Path) -> MaterializationTarget:
    renderer = meta.get("renderer")
    path = meta.get("path")
    path_base = meta.get("path_base", "documentation_root")
    if not isinstance(renderer, str) or not renderer:
        raise ResourceError(f"{source}: materialization renderer must be a non-empty string")
    if not isinstance(path, str) or not path:
        raise ResourceError(f"{source}: materialization path must be a non-empty string")
    if path_base != "documentation_root":
        raise ResourceError(f"{source}: v0.1 materialization path_base must be 'documentation_root'")
    try:
        candidate = confined_path(roots.documentation_root, path)
        structured_root = confined_path(roots.documentation_root, roots.config.structured_dir)
        dependency_root = confined_path(roots.documentation_root, roots.config.dependency_dir)
    except RootDiscoveryError as exc:
        raise ResourceError(f"{source}: unsafe materialization path {path!r}: {exc}") from exc
    for reserved_name, reserved_root in (("structured", structured_root), ("dependency", dependency_root)):
        if candidate == reserved_root or is_within(candidate, reserved_root):
            raise ResourceError(
                f"{source}: materialization path {path!r} targets reserved {reserved_name} state under documentation root"
            )
    if "\\" in path:
        raise ResourceError(f"{source}: materialization path must use '/' separators")
    posix = PurePosixPath(path)
    if posix.is_absolute() or ".." in posix.parts or "." in posix.parts:
        raise ResourceError(f"{source}: materialization path must be documentation-root-relative")
    canonical = posix.as_posix()
    if canonical != path:
        raise ResourceError(f"{source}: materialization path must already be canonical: {canonical!r}")
    return MaterializationTarget(renderer=renderer, path=canonical, path_base=path_base)


def load_managed_resource(path: Path, *, roots: ProjectRoots) -> ManagedResource:
    path = path.resolve(strict=True)
    structured_root = (roots.documentation_root / roots.config.structured_dir).resolve(strict=False)
    try:
        path.relative_to(structured_root)
    except ValueError as exc:
        raise ResourceError(f"managed resource must live under {structured_root}: {path}") from exc

    value = _load_json(path)
    _validate_envelope(value, source=path)
    meta: dict[str, Any] = value["$docengine"]
    schema_uri = meta.get("schema")
    if schema_uri:
        registry = ProjectSchemaRegistry(roots.project_root, roots.config.schemas)
        try:
            registry.validate(schema_uri, value["data"])
        except (SchemaResolutionError, SchemaValidationError) as exc:
            raise ResourceError(f"{path}: schema validation failed: {exc}") from exc

    targets = tuple(_target_from_meta(item, roots=roots, source=path) for item in meta["materialize"])
    markdown_targets = [target.path for target in targets if target.renderer == "markdown"]
    if markdown_targets:
        mirrored = path.relative_to(structured_root).with_suffix(".md").as_posix()
        if markdown_targets != [mirrored]:
            raise ResourceError(
                f"{path}: mirrored _structured convention requires the single markdown target {mirrored!r}; "
                f"got {markdown_targets!r}"
            )
    raw = RawObject.create(
        resource_id=meta["resource_id"],
        source_path=path,
        schema_uri=schema_uri,
        resource_kind=meta.get("resource_kind", "structured"),
        data=value["data"],
    )
    return ManagedResource(
        raw=raw,
        source_relative=path.relative_to(roots.documentation_root).as_posix(),
        targets=targets,
        source_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


class ResourceCatalog:
    def __init__(self, roots: ProjectRoots):
        self.roots = roots
        self._managed: dict[str, ManagedResource] = {}
        self._items: tuple[ResourceInventoryItem, ...] = ()
        self._plain_files: frozenset[str] = frozenset()

    @classmethod
    def scan(cls, roots: ProjectRoots) -> "ResourceCatalog":
        catalog = cls(roots)
        docs = roots.documentation_root
        structured = docs / roots.config.structured_dir
        if structured.exists():
            structured_resolved = structured.resolve(strict=True)
            if not is_within(structured_resolved, docs.resolve(strict=False)):
                raise ResourceError("structured resource directory escapes documentation root")
            for path in sorted(structured.rglob("*.json"), key=lambda p: p.as_posix()):
                resource = load_managed_resource(path, roots=roots)
                if resource.resource_id in catalog._managed:
                    other = catalog._managed[resource.resource_id]
                    raise ResourceError(
                        f"duplicate resource_id {resource.resource_id!r}: {other.source_relative} and {resource.source_relative}"
                    )
                catalog._managed[resource.resource_id] = resource

        generated_targets: dict[str, ManagedResource] = {}
        for resource in catalog._managed.values():
            for target in resource.targets:
                if target.path in generated_targets:
                    other = generated_targets[target.path]
                    raise ResourceError(
                        f"duplicate materialization target {target.path!r}: {other.resource_id} and {resource.resource_id}"
                    )
                generated_targets[target.path] = resource

        items: list[ResourceInventoryItem] = []
        for resource in catalog._managed.values():
            items.append(ResourceInventoryItem(
                kind=resource.kind,
                ref=str(resource.raw.ref),
                source=resource.source_relative,
                resource_id=resource.resource_id,
            ))
            for target in resource.targets:
                items.append(ResourceInventoryItem(
                    kind="generated",
                    ref=f"file://{target.path}",
                    source=target.path,
                    owner_ref=str(resource.raw.ref),
                    renderer=target.renderer,
                ))

        reserved_roots = {
            (docs / roots.config.structured_dir).resolve(strict=False),
            (docs / roots.config.dependency_dir).resolve(strict=False),
        }
        if docs.exists():
            for md in sorted(docs.rglob("*.md"), key=lambda p: p.as_posix()):
                resolved = md.resolve(strict=False)
                if not is_within(resolved, docs.resolve(strict=False)):
                    raise ResourceError(f"documentation file escapes documentation root through symlink: {md}")
                if any(resolved == rr or rr in resolved.parents for rr in reserved_roots):
                    continue
                relative = md.relative_to(docs).as_posix()
                if relative in generated_targets:
                    continue
                items.append(ResourceInventoryItem(kind="plain", ref=f"file://{relative}", source=relative))

        catalog._items = tuple(sorted(items, key=lambda item: (item.kind, item.ref)))
        catalog._plain_files = frozenset(
            item.source for item in catalog._items if item.kind == "plain" and item.source is not None
        )
        return catalog

    @property
    def items(self) -> tuple[ResourceInventoryItem, ...]:
        return self._items

    @property
    def managed(self) -> tuple[ManagedResource, ...]:
        return tuple(self._managed[key] for key in sorted(self._managed))

    def resolve(self, ref: ResourceRef | str) -> Any:
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if resource_ref.scheme == "resource":
            logical_id = resource_ref.logical_resource_id
            assert logical_id is not None
            try:
                resource = self._managed[logical_id]
            except KeyError as exc:
                raise ResourceError(f"unknown resource: {logical_id}") from exc
            if resource.raw.resource_kind == "derived_descriptor":
                raise ResourceError(
                    f"derived descriptor {resource.raw.ref} is metadata-only and has no raw domain value; "
                    "resolve it through a registered builder"
                )
            if not resource_ref.pointer_parts:
                return resource.raw
            return resource.raw.read(resource_ref)
        if resource_ref.scheme == "file":
            assert resource_ref.file_path is not None
            if resource_ref.file_path not in self._plain_files:
                raise ResourceError(
                    "file:// refs may address only plain canonical Markdown in v0.1; "
                    f"use resource:// for managed/derived documentation: {resource_ref.file_path}"
                )
            try:
                path = confined_path(self.roots.documentation_root, resource_ref.file_path)
            except RootDiscoveryError as exc:
                raise ResourceError(str(exc)) from exc
            if not path.is_file():
                raise ResourceError(f"unknown documentation file: {resource_ref.file_path}")
            return path.read_text(encoding="utf-8")
        raise ResourceError(f"unsupported ref scheme: {resource_ref.scheme}")

    def get(self, ref: ResourceRef | str) -> Any:
        return self.resolve(ref)

    def version(self, ref: ResourceRef | str) -> str:
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if resource_ref.scheme == "resource":
            logical_id = resource_ref.logical_resource_id
            assert logical_id is not None
            try:
                resource = self._managed[logical_id]
            except KeyError as exc:
                raise ResourceError(f"unknown resource: {logical_id}") from exc
            if resource.raw.resource_kind == "derived_descriptor":
                raise ResourceError(
                    f"derived descriptor {resource.raw.ref} is metadata-only and has no raw domain version; "
                    "resolve it through a registered builder"
                )
            if not resource_ref.pointer_parts:
                # Dependency identity follows the canonical domain object, not the
                # physical JSON representation or $docengine materialization metadata.
                return _canonical_value_hash(resource.raw.data)
            value = resource.raw.read(resource_ref)
            return _canonical_value_hash(value)
        if resource_ref.scheme == "file":
            assert resource_ref.file_path is not None
            if resource_ref.file_path not in self._plain_files:
                raise ResourceError(
                    "file:// refs may address only plain canonical Markdown in v0.1; "
                    f"use resource:// for managed/derived documentation: {resource_ref.file_path}"
                )
            path = confined_path(self.roots.documentation_root, resource_ref.file_path)
            if not path.is_file():
                raise ResourceError(f"unknown documentation file: {resource_ref.file_path}")
            return hashlib.sha256(path.read_bytes()).hexdigest()
        raise ResourceError(f"unsupported ref scheme: {resource_ref.scheme}")

    def to_payload(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for item in self._items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
        return {
            "roots": self.roots.to_dict(),
            "counts": dict(sorted(counts.items())),
            "resources": [item.to_dict() for item in self._items],
        }
