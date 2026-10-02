"""Project configuration contract for docengine.toml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import re
import tomllib


class ProjectConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    documentation_root: str = "docs"
    structured_dir: str = "_structured"
    dependency_dir: str = "_dependency"
    project_package: str = "docengine_project"
    schemas: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


def load_project_config(project_root: str | Path) -> ProjectConfig:
    root = Path(project_root).expanduser().resolve(strict=False)
    path = root / "docengine.toml"
    if path.is_symlink():
        raise ProjectConfigError("docengine.toml must be a regular project-owned file, not a symlink")
    if not path.exists():
        return ProjectConfig()
    try:
        path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise ProjectConfigError("docengine.toml must be a project-owned file inside project root") from exc
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProjectConfigError(f"invalid docengine.toml: {exc}") from exc
    block = raw.get("docengine", {})
    if not isinstance(block, dict):
        raise ProjectConfigError("[docengine] must be a TOML table")
    schemas = raw.get("schemas", {})
    if not isinstance(schemas, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in schemas.items()
    ):
        raise ProjectConfigError("[schemas] must map non-empty schema URI strings to non-empty project-relative path strings")
    allowed = {"documentation_root", "structured_dir", "dependency_dir", "project_package", "config_version"}
    unknown = set(block) - allowed
    if unknown:
        raise ProjectConfigError(f"unknown [docengine] keys: {sorted(unknown)}")
    if "config_version" in block and block["config_version"] != 1:
        raise ProjectConfigError(f"unsupported docengine config_version: {block['config_version']!r}")
    values = {
        "documentation_root": block.get("documentation_root", "docs"),
        "structured_dir": block.get("structured_dir", "_structured"),
        "dependency_dir": block.get("dependency_dir", "_dependency"),
        "project_package": block.get("project_package", "docengine_project"),
    }
    path_values = {key: values[key] for key in ("documentation_root", "structured_dir", "dependency_dir")}
    if not all(isinstance(v, str) and v and not Path(v).is_absolute() for v in path_values.values()):
        raise ProjectConfigError("documentation_root/structured_dir/dependency_dir must be non-empty relative paths")
    if not isinstance(values["project_package"], str) or not values["project_package"]:
        raise ProjectConfigError("project_package must be a non-empty dotted Python package name")
    for key in ("documentation_root", "structured_dir", "dependency_dir"):
        value = values[key]
        if "\\" in value:
            raise ProjectConfigError(f"{key} must use '/' separators")
        if ".." in Path(value).parts:
            raise ProjectConfigError(f"{key} must not contain '..'")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", values["project_package"]):
        raise ProjectConfigError("project_package must be a canonical dotted Python package name")
    if Path(values["structured_dir"]) == Path(".") or Path(values["dependency_dir"]) == Path("."):
        raise ProjectConfigError("structured_dir/dependency_dir must be dedicated subdirectories, not documentation root itself")

    structured_parts = Path(values["structured_dir"]).parts
    dependency_parts = Path(values["dependency_dir"]).parts
    if (
        structured_parts == dependency_parts
        or structured_parts[: len(dependency_parts)] == dependency_parts
        or dependency_parts[: len(structured_parts)] == structured_parts
    ):
        raise ProjectConfigError("structured_dir and dependency_dir must be disjoint documentation subtrees")

    return ProjectConfig(**values, schemas=MappingProxyType(dict(schemas)))


def render_project_config(*, documentation_root: str = "docs") -> str:
    escaped = documentation_root.replace("\\", "/").replace('"', '\\"')
    return (
        "[docengine]\n"
        "config_version = 1\n"
        f'documentation_root = "{escaped}"\n'
        'structured_dir = "_structured"\n'
        'dependency_dir = "_dependency"\n'
        'project_package = "docengine_project"\n'
        "\n"
        "[schemas]\n"
        "# Register project schema URIs here, for example:\n"
        '# "project://schemas/example/v1" = "docengine_project/schemas/example.schema.json"\n'
    )
