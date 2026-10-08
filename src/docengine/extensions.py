"""Load project-owned builder code from a confined local package."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType

from .builders import BuilderRegistry, BuilderRegistrationError
from .project import ProjectRoots, is_within
from .resources import ResourceCatalog
from .semantic import SemanticDependencyRegistry, SemanticRuleError
from .materialization import RendererRegistry, RendererRegistrationError


_PROJECT_PACKAGE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


class ProjectExtensionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LoadedProjectExtension:
    package: str
    source_path: Path
    source_revision: str
    registry: BuilderRegistry
    semantic_registry: SemanticDependencyRegistry
    renderer_registry: RendererRegistry


def _package_paths(roots: ProjectRoots) -> tuple[tuple[str, ...], Path, Path, Path]:
    package = roots.config.project_package
    if not _PROJECT_PACKAGE_RE.fullmatch(package):
        raise ProjectExtensionError(f"invalid project_package dotted name: {package!r}")
    parts = tuple(package.split("."))
    current = roots.project_root
    top_dir: Path | None = None
    for segment in parts:
        current = current / segment
        if top_dir is None:
            top_dir = current
        init = current / "__init__.py"
        if current.is_symlink() or init.is_symlink():
            raise ProjectExtensionError("project_package and each package __init__.py must not be symlinks")
        if not current.is_dir() or not init.is_file():
            raise ProjectExtensionError(
                f"configured project_package {package!r} must be an importable local package; "
                f"missing package segment or __init__.py at {current}"
            )
    assert top_dir is not None
    package_dir = current
    init_path = package_dir / "__init__.py"
    resolved_dir = package_dir.resolve(strict=True)
    resolved_init = init_path.resolve(strict=True)
    resolved_top = top_dir.resolve(strict=True)
    project = roots.project_root.resolve(strict=True)
    if not is_within(resolved_dir, project) or not is_within(resolved_init, project):
        raise ProjectExtensionError("project_package escapes project root")
    docs = roots.documentation_root.resolve(strict=False)
    if resolved_dir == docs or is_within(resolved_dir, docs) or resolved_top == docs or is_within(resolved_top, docs):
        raise ProjectExtensionError("project_package must live outside the documentation root")
    for entry in top_dir.rglob("*"):
        if entry.is_symlink():
            raise ProjectExtensionError(f"project_package contains symlinked code/data: {entry.relative_to(top_dir)}")
        try:
            resolved = entry.resolve(strict=True)
        except OSError as exc:
            raise ProjectExtensionError(f"project_package contains unreadable entry: {entry}") from exc
        if not is_within(resolved, resolved_top):
            raise ProjectExtensionError(f"project_package entry escapes package root: {entry}")
    return parts, resolved_top, resolved_dir, resolved_init


def _package_revision(top_dir: Path) -> str:
    """Hash project-owned Python source that can influence registered builders.

    For dotted packages we hash the whole top-level package so parent-relative helper
    modules are covered too. Generated caches are intentionally excluded.
    """

    digest = hashlib.sha256()
    py_files = sorted((p for p in top_dir.rglob("*.py") if p.is_file()), key=lambda p: p.relative_to(top_dir).as_posix())
    for path in py_files:
        rel = path.relative_to(top_dir).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _load_module(roots: ProjectRoots) -> tuple[ModuleType, Path, str]:
    parts, top_dir, _, init_path = _package_paths(roots)
    project = roots.project_root.resolve(strict=True)
    token_material = f"{project}\0{roots.config.project_package}".encode("utf-8")
    prefix = f"_docengine_project_{hashlib.sha256(token_material).hexdigest()[:16]}"

    # Always load a fresh project-local package tree for deterministic temp-project/test behavior.
    for key in [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]:
        sys.modules.pop(key, None)

    # Synthetic private root preserves isolation while allowing normal relative imports
    # inside dotted project packages (including ``from ..common import ...``).
    root_module = ModuleType(prefix)
    root_module.__package__ = prefix
    root_module.__path__ = [str(project)]  # type: ignore[attr-defined]
    sys.modules[prefix] = root_module

    loaded: ModuleType | None = None
    previous_dont_write_bytecode = sys.dont_write_bytecode
    try:
        # Loading project-owned semantics is part of read-only commands such as
        # verify/explain/graph. Never leave __pycache__ artifacts in the project
        # merely by inspecting it.
        sys.dont_write_bytecode = True
        current = project
        for index, segment in enumerate(parts):
            current = current / segment
            current_init = current / "__init__.py"
            full_name = prefix + "." + ".".join(parts[: index + 1])

            # A parent package may legitimately import the configured child from its
            # own ``__init__.py``. Reuse that already-loaded module rather than
            # executing the child package a second time.
            existing = sys.modules.get(full_name)
            if existing is not None:
                existing_file = getattr(existing, "__file__", None)
                if existing_file is None or Path(existing_file).resolve(strict=True) != current_init.resolve(strict=True):
                    raise ProjectExtensionError(
                        f"project package module collision for {full_name}: expected {current_init}, got {existing_file}"
                    )
                loaded = existing
                continue

            spec = importlib.util.spec_from_file_location(
                full_name,
                current_init,
                submodule_search_locations=[str(current)],
            )
            if spec is None or spec.loader is None:
                raise ProjectExtensionError(f"cannot load project package from {current_init}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = module
            spec.loader.exec_module(module)
            loaded = module
    except SystemExit as exc:
        for key in [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]:
            sys.modules.pop(key, None)
        raise ProjectExtensionError(f"project package import exited: {exc}") from exc
    except Exception as exc:
        for key in [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]:
            sys.modules.pop(key, None)
        if isinstance(exc, ProjectExtensionError):
            raise
        raise ProjectExtensionError(f"project package import failed: {exc}") from exc
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode

    assert loaded is not None
    return loaded, init_path, _package_revision(top_dir)


def _validate_registered_targets(registry: BuilderRegistry, catalog: ResourceCatalog) -> None:
    managed_by_id = {resource.resource_id: resource for resource in catalog.managed}
    registered_ids = {
        spec.target.logical_resource_id
        for spec in registry.specs
        if spec.target.logical_resource_id is not None
    }

    # Internal-only derived objects do not need documentation JSON. If a target *is*
    # documentation-owned, its descriptor must explicitly identify it as derived.
    for spec in registry.specs:
        logical_id = spec.target.logical_resource_id
        assert logical_id is not None
        resource = managed_by_id.get(logical_id)
        if resource is None:
            continue
        if resource.raw.resource_kind != "derived_descriptor":
            raise ProjectExtensionError(
                f"builder target {spec.target} must be declared resource_kind='derived_descriptor', "
                f"not {resource.raw.resource_kind!r}"
            )

    # Conversely, a derived descriptor is not raw domain data. Once project code is
    # loaded it must have a builder rather than silently resolving to descriptor.data.
    for resource in catalog.managed:
        if resource.raw.resource_kind == "derived_descriptor" and resource.resource_id not in registered_ids:
            raise ProjectExtensionError(
                f"derived descriptor {resource.raw.ref} has no registered builder"
            )


def _validate_semantic_rules(semantic_registry: SemanticDependencyRegistry, catalog: ResourceCatalog, builders: BuilderRegistry) -> None:
    # Registration validates canonical reference syntax, comparator ids, duplicate
    # targets/sources and semantic-rule cycles. Current source/target availability is
    # intentionally a runtime concern: deleting or temporarily breaking a reviewed
    # target must remain diagnosable as target/source unavailable rather than making
    # the whole project extension impossible to load.
    semantic_registry.validate_cycles()
    builder_targets = {str(spec.target) for spec in builders.specs}
    for rule in semantic_registry.rules:
        if str(rule.target) in builder_targets:
            raise ProjectExtensionError(
                f"semantic rule target {rule.target} is also a deterministic builder target; "
                "v0.1 requires distinct exact targets because dependency state selects one active receipt per target"
            )


def load_project_extension(roots: ProjectRoots, catalog: ResourceCatalog, *, include_renderers: bool = True) -> LoadedProjectExtension:
    module, source_path, source_revision = _load_module(roots)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    try:
        # Registration callbacks may lazily import helper modules.  Inspection commands
        # are read-only, so suppress bytecode writes for the full registration phase,
        # not only for the package __init__ import.
        sys.dont_write_bytecode = True

        register = getattr(module, "register_builders", None)
        if register is None or not callable(register):
            raise ProjectExtensionError(
                f"project package {roots.config.project_package!r} must expose callable register_builders(registry)"
            )
        registry = BuilderRegistry(source_revision=source_revision)
        registry.bind_revision_check(lambda: _package_revision(_package_paths(roots)[1]))
        try:
            outcome = register(registry)
        except BuilderRegistrationError:
            raise
        except SystemExit as exc:
            raise ProjectExtensionError(f"register_builders exited: {exc}") from exc
        except Exception as exc:
            raise ProjectExtensionError(f"register_builders failed: {exc}") from exc
        if outcome is not None:
            raise ProjectExtensionError("register_builders(registry) must mutate the supplied registry and return None")
        _validate_registered_targets(registry, catalog)

        semantic_registry = SemanticDependencyRegistry()
        register_semantic = getattr(module, "register_semantic_dependencies", None)
        if register_semantic is not None:
            if not callable(register_semantic):
                raise ProjectExtensionError("register_semantic_dependencies must be callable when defined")
            try:
                semantic_outcome = register_semantic(semantic_registry)
            except SemanticRuleError:
                raise
            except SystemExit as exc:
                raise ProjectExtensionError(f"register_semantic_dependencies exited: {exc}") from exc
            except Exception as exc:
                raise ProjectExtensionError(f"register_semantic_dependencies failed: {exc}") from exc
            if semantic_outcome is not None:
                raise ProjectExtensionError(
                    "register_semantic_dependencies(registry) must mutate the supplied registry and return None"
                )
        _validate_semantic_rules(semantic_registry, catalog, registry)

        renderer_registry = RendererRegistry(source_revision=source_revision)
        if include_renderers:
            register_renderers = getattr(module, "register_renderers", None)
            if register_renderers is not None:
                if not callable(register_renderers):
                    raise ProjectExtensionError("register_renderers must be callable when defined")
                try:
                    renderer_outcome = register_renderers(renderer_registry)
                except RendererRegistrationError:
                    raise
                except SystemExit as exc:
                    raise ProjectExtensionError(f"register_renderers exited: {exc}") from exc
                except Exception as exc:
                    raise ProjectExtensionError(f"register_renderers failed: {exc}") from exc
                if renderer_outcome is not None:
                    raise ProjectExtensionError(
                        "register_renderers(registry) must mutate the supplied registry and return None"
                    )

            # Fail at extension-load time when a documentation-owned target names an unknown
            # renderer. Dependency/semantic diagnostics may deliberately skip renderer
            # registration so a broken P5 presentation extension cannot erase P3/P4 evidence.
            for resource in catalog.managed:
                for target in resource.targets:
                    try:
                        renderer_registry.get(target.renderer)
                    except RendererRegistrationError as exc:
                        raise ProjectExtensionError(
                            f"materialization target {target.path!r} for {resource.raw.ref} uses unknown renderer {target.renderer!r}"
                        ) from exc

        return LoadedProjectExtension(
            package=roots.config.project_package,
            source_path=source_path,
            source_revision=source_revision,
            registry=registry,
            semantic_registry=semantic_registry,
            renderer_registry=renderer_registry,
        )
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode


__all__ = ["LoadedProjectExtension", "ProjectExtensionError", "load_project_extension"]
