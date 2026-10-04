# Storage Model

## 1. Рекомендуемая project layout

```text
project/
  docs/
    README.md
    architecture/
      overview.md
      rationale.md
    policies/
      method_policy.md

    _structured/
      architecture/
        overview.json
      policies/
        method_policy.json

    _dependency/
      state/
        dependency_state.json
      baselines/
        ...content-addressed or target-scoped snapshots...
      events/
        dependency_events.jsonl
      receipts/
        dependency_receipts.jsonl

  docengine_project/
    schemas/
    models/
    builders/
    validators/
    renderers/
    dependency_rules/

  src/docengine/            # reusable engine code if vendored/local
```

`docs/_structured` и `docs/_dependency` являются частью **documentation state**, а не программного пакета engine.

## 2. Почему не класть JSON рядом с engine code

Structured JSON описывает содержание документации конкретного проекта. Оно должно путешествовать вместе с документацией и быть понятно как её canonical machine-readable component.

## 3. Почему отдельный `_structured/`, а не JSON рядом с каждым Markdown

Оба варианта технически возможны. Default v0.1 — mirrored `_structured/`, потому что:

- human-facing folders остаются чистыми;
- JSON явно относится к documentation, а не runtime code;
- структура остаётся предсказуемой;
- можно легко найти все managed resources;
- удобно clean regenerate views.

Если проекту нужна co-location, adapter policy может разрешить `architecture/_data/overview.json`, но это не default.

## 4. Managed resource envelope

```json
{
  "$docengine": {
    "resource_id": "architecture.overview",
    "schema": "project://schemas/architecture-overview/v1",
    "materialize": [
      {
        "renderer": "markdown",
        "path": "architecture/overview.md",
        "path_base": "documentation_root"
      }
    ]
  },
  "data": {
    "title": "Architecture Overview",
    "sections": []
  }
}
```

### `$docengine`
Engine metadata only.

### `data`
Domain/document data only.

Dependency declarations не размещаются здесь по умолчанию.

## 5. Output path

`$docengine.materialize[].path` для v0.1 является путём **от корня документации**. Рекомендуемый явный metadata: `path_base: "documentation_root"`. Это устраняет `../../`, делает ресурсы переносимее и упрощает confinement/parity checks.

Engine обязан проверять path confinement: materialization target не должен выходить за configured documentation root без специального permission.

## 6. Plain Markdown

Plain Markdown может не иметь никаких sidecar-файлов.

Whole-file dependency на plain Markdown регистрируется code rule и baseline snapshot; JSON target не требуется.

## 7. Derived file descriptors

Если builder создаёт derived object, который должен materialize в Markdown/другой файл документации, output ownership/path не должен быть спрятан только в Python-коде. Создаётся descriptor JSON в зеркальном `docs/_structured/...` с `resource_kind: "derived_descriptor"`, `resource_id` и `$docengine.materialize[]`. Формула/зависимости остаются в project code. Внутренние derived objects без файлового output descriptor не требуют.

## 8. P1 project configuration

Project-level engine configuration lives at `project/docengine.toml`; documentation-owned content/state remains under the configured documentation root.

Canonical v0.1 fields:

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

Filesystem paths in `[docengine]` are project-relative and may not escape the project. `project_package` names project-owned executable semantics and P2 requires that package to live outside the documentation root. Schema files are project-owned code/contracts, while structured documentation instances remain under `docs/_structured/`.

`docengine init` creates the config plus `_structured` and `_dependency/{state,baselines,receipts,events}` directories. It does **not** create JSON sidecars for existing Markdown.

## 9. Mirrored `_structured` rule in v0.1

For a structured resource with a Markdown materialization target, the source and target must mirror one another:

```text
docs/_structured/architecture/overview.json
                    ↓
docs/architecture/overview.md
```

The destination itself is still declared explicitly by `$docengine.materialize[].path`; the mirror rule prevents an apparently local structured source from silently owning an unrelated documentation path.

## 10. Mirrored project-code rule for AI/project authoring

Structured data and executable project semantics remain physically separated, but use the same logical target path for discoverability:

```text
docs/<logical/path>.md
docs/_structured/<logical/path>.json
docengine_project/builders/<logical/path>.py
docengine_project/dependency_rules/<logical/path>.py
```

The deterministic builder path is organized by the **produced target**, not by whichever upstream source happens to be read. The exact semantic rule subtree is `dependency_rules/` in the v0.1 storage model.

File placement does not register code by itself. Nested modules must be aggregated/imported by the project package `register_builders(registry)` / `register_semantic_dependencies(registry)` surface.

Project code must remain outside the documentation root; this is an ownership/confinement rule, not a Python security sandbox.

## Reserved documentation-owned subtrees

`structured_dir` and `dependency_dir` are disjoint reserved subtrees. Materialization targets may not write into either subtree, regardless of renderer. This prevents generated output from overwriting canonical structured JSON or dependency runtime state.



## P5 generated-view state

Generated-view ownership remains declared in `$docengine.materialize[]`. Runtime digest/provenance lives under `docs/_dependency/state/materialization_state.json`; generated content itself remains at the declared documentation-root-relative target path. No visible generated marker is required. Removed targets are preserved and reported as orphaned state rather than auto-deleted. Acknowledgment is explicit and provenance-preserving: `orphan_acknowledged=true` remains in materialization state instead of deleting the old ownership record.


## P7 hardening state

Machine-owned hardening evidence lives under `docs/_dependency/hardening/`:

```text
runtime_layout.json
migration_events.jsonl
recovery_events.jsonl
transactions/          # transient crash journals; empty in a clean package
```

The process lock itself is external to the project so read-only commands do not create project files. Open transaction journals are recovery evidence, not disposable cache.
