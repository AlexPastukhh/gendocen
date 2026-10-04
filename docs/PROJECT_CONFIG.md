# Project Configuration Contract — P2

## Location

`docengine.toml` lives in the project root. It configures the engine, but it does not own documentation content; canonical structured documentation remains under the documentation root.

## v0.1 contract

```toml
[docengine]
config_version = 1
documentation_root = "docs"
structured_dir = "_structured"
dependency_dir = "_dependency"
project_package = "docengine_project"

[schemas]
"project://schemas/example/v1" = "docengine_project/schemas/example.schema.json"
```

### `[docengine]`

- `config_version` — currently exactly `1`.
- `documentation_root` — project-relative path; default `docs`.
- `structured_dir` — documentation-root-relative structured-data directory; default `_structured`.
- `dependency_dir` — documentation-root-relative runtime state directory; default `_dependency`.
- `project_package` — dotted project-local Python package that owns builder/validator/renderer semantics; default `docengine_project`. P2 loads it only from inside project root. Dotted packages retain normal relative-import semantics under an isolated private runtime prefix.

Absolute paths and `..` traversal are rejected for filesystem configuration fields. `project_package` must be a canonical dotted Python package name. Paths use `/` separators for portable canonical configuration. `structured_dir` and `dependency_dir` must be dedicated, disjoint documentation subtrees: neither may be `.` and neither may equal or contain the other.

### `[schemas]`

Maps a schema URI stored in `$docengine.schema` to a project-relative JSON schema file. Schema paths are resolved with project-root confinement. A declared but unregistered schema is an error; validation is never silently skipped.

P1 ships a dependency-free strict validator for the deliberately small v0.1 JSON-Schema subset: `type`, `required`, `properties`, `additionalProperties`, `items`, `enum`, `minLength`, `minItems`, `maxItems`, and `uniqueItems` plus annotation fields. Unsupported semantic keywords fail explicitly instead of being ignored. A richer schema adapter can be added without changing managed JSON.

## Root discovery

Precedence:

1. explicit `--project-root` / `--docs-root`;
2. upward search for `docengine.toml` from cwd without crossing filesystem-device boundaries;
3. current directory + default `docs` when no marker exists.

The configured documentation root must stay inside the project root in v0.1. Explicit string overrides for both `--project-root` and `--docs-root` must be non-empty and non-whitespace; empty explicit values are usage/config errors (exit `4` at the CLI boundary), not fallback/default selection. An explicit project root must already exist and be a directory. A non-empty documentation-root path may be absent for an empty/uninitialized documentation tree, but if it exists it must be a directory rather than a regular file. Explicit `--docs-root .` remains a valid deliberate override that selects the project root itself as the documentation root.

## Initialization

`docengine init` is idempotent. It creates config/runtime directories when absent, reports existing compatible state when rerun, rejects conflicting/invalid config, and does not transform plain Markdown into managed resources.

## Project package loading (P2)

The configured package must exist below project root, contain `__init__.py` at every dotted package segment, and contain no symlinked entries. P2 expects callable `register_builders(registry)`. Internal-only builder targets may exist without documentation JSON. If a matching documentation resource exists, it must be `resource_kind="derived_descriptor"`; every existing derived descriptor must have a registered builder once the extension is loaded.
