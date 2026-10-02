"""Project/documentation root discovery and initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig, ProjectConfigError, load_project_config, render_project_config


DEFAULT_CONFIG_NAMES = ("docengine.toml",)


class RootDiscoveryError(ValueError):
    """Raised when project/documentation roots are unsafe or ambiguous."""


class ProjectInitializationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectRoots:
    project_root: Path
    documentation_root: Path
    source: str
    config: ProjectConfig

    def to_dict(self) -> dict[str, str]:
        return {
            "project_root": str(self.project_root),
            "documentation_root": str(self.documentation_root),
            "source": self.source,
        }


def _resolved(path: str | Path, *, base: Path | None = None) -> Path:
    source = Path(path).expanduser()
    if not source.is_absolute() and base is not None:
        source = base / source
    return source.resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def confined_path(root: str | Path, relative_path: str | Path) -> Path:
    root_path = _resolved(root)
    relative = Path(relative_path)
    if relative.is_absolute():
        raise RootDiscoveryError(f"path must be relative to configured root: {relative_path}")
    candidate = _resolved(relative, base=root_path)
    if not is_within(candidate, root_path):
        raise RootDiscoveryError(f"path escapes configured root: {relative_path}")
    return candidate


def _find_project_root(current: Path) -> tuple[Path, str]:
    try:
        origin_device = current.stat().st_dev
    except OSError:
        origin_device = None
    for candidate in (current, *current.parents):
        try:
            if origin_device is not None and candidate.stat().st_dev != origin_device:
                break
        except OSError:
            break
        # A lexically present marker (including dangling symlink or wrong file type)
        # must stop discovery so load_project_config can reject it explicitly rather
        # than silently treating a nested cwd as a new project.
        if any((candidate / name).exists() or (candidate / name).is_symlink() for name in DEFAULT_CONFIG_NAMES):
            return candidate, "config_marker"
    return current, "cwd"


def discover_roots(
    *,
    cwd: str | Path | None = None,
    project_root: str | Path | None = None,
    docs_root: str | Path | None = None,
) -> ProjectRoots:
    """Discover project/docs roots without mutating the filesystem.

    Precedence: explicit project/docs roots > docengine.toml > upward search/defaults.
    All documentation roots are confined to the project root in v0.1.
    """

    current = _resolved(cwd or Path.cwd())
    if project_root is not None:
        project = _resolved(project_root, base=current)
        source = "explicit"
    else:
        project, source = _find_project_root(current)

    if not project.exists() or not project.is_dir():
        raise RootDiscoveryError(f"project root does not exist or is not a directory: {project}")

    try:
        config = load_project_config(project)
    except ProjectConfigError as exc:
        raise RootDiscoveryError(str(exc)) from exc

    if docs_root is not None:
        documentation = _resolved(docs_root, base=project)
        docs_source = "explicit_docs"
    else:
        documentation = _resolved(config.documentation_root, base=project)
        docs_source = "config" if (project / "docengine.toml").exists() else "default"

    if not is_within(documentation, project):
        raise RootDiscoveryError("documentation root must be inside project root")
    if documentation.exists() and not documentation.is_dir():
        raise RootDiscoveryError(f"documentation root exists but is not a directory: {documentation}")

    return ProjectRoots(
        project_root=project,
        documentation_root=documentation,
        source=source,
        config=config,
    )


@dataclass(frozen=True, slots=True)
class InitResult:
    roots: ProjectRoots
    created: tuple[str, ...]
    existing: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.created)


def initialize_project(
    *,
    cwd: str | Path | None = None,
    project_root: str | Path | None = None,
    docs_root: str | Path | None = None,
) -> InitResult:
    """Create the v0.1 project contract without promoting plain Markdown."""

    current = _resolved(cwd or Path.cwd())
    if project_root is not None:
        project = _resolved(project_root, base=current)
    else:
        project, _ = _find_project_root(current)
    if not project.exists() or not project.is_dir():
        raise ProjectInitializationError(f"project root does not exist or is not a directory: {project}")

    config_path = project / "docengine.toml"
    if config_path.is_symlink():
        raise ProjectInitializationError("docengine.toml symlinks are not allowed for initialization in v0.1")
    requested_docs = _resolved(docs_root or "docs", base=project)
    if not is_within(requested_docs, project):
        raise ProjectInitializationError("documentation root must be inside project root")

    created: list[str] = []
    existing: list[str] = []

    if config_path.exists():
        try:
            config = load_project_config(project)
        except ProjectConfigError as exc:
            raise ProjectInitializationError(str(exc)) from exc
        configured_docs = _resolved(config.documentation_root, base=project)
        if docs_root is not None and configured_docs != requested_docs:
            raise ProjectInitializationError(
                f"existing docengine.toml uses documentation_root={config.documentation_root!r}; "
                f"requested {requested_docs.relative_to(project).as_posix()!r}"
            )
        existing.append("docengine.toml")
    else:
        relative_docs = requested_docs.relative_to(project).as_posix()
        config_path.write_text(render_project_config(documentation_root=relative_docs), encoding="utf-8")
        created.append("docengine.toml")
        config = load_project_config(project)

    documentation = _resolved(config.documentation_root, base=project)
    if not is_within(documentation, project):
        raise ProjectInitializationError("configured documentation root escapes project root")
    paths = (
        documentation,
        documentation / config.structured_dir,
        documentation / config.dependency_dir / "state",
        documentation / config.dependency_dir / "baselines",
        documentation / config.dependency_dir / "receipts",
        documentation / config.dependency_dir / "events",
    )
    for path in paths:
        if not is_within(path.resolve(strict=False), documentation.resolve(strict=False)) and path != documentation:
            raise ProjectInitializationError(f"runtime path escapes documentation root: {path}")
        rel = path.relative_to(project).as_posix()
        if path.exists():
            if not path.is_dir():
                raise ProjectInitializationError(f"expected directory but found file: {rel}")
            existing.append(rel)
        else:
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel)

    roots = discover_roots(project_root=project)
    return InitResult(roots=roots, created=tuple(created), existing=tuple(existing))
