# Documentation Engine Use Cases

Registry version: `0.3.0`; contract version: `1.1.0`.

## DOC01 — Initialize documentation project

**Implementation target:** `v0.1`
**Group / interaction:** `lifecycle` / `orchestration`
**Intent:** Подключить engine к существующей документации без требования структурировать все Markdown.
**CLI/API surface:** `docengine init`
**Machine CLI commands:** `init`

**Preconditions:**
- _none_

**Inputs:**
- documentation_root
- optional project config

**Reads:**
- filesystem documentation tree

**Writes:**
- engine project config
- runtime directories

**Outputs:**
- initialized project descriptor

**Side effects:**
- create docs/_dependency if configured

**Failure modes:**
- root_not_writable
- path_escape
- invalid_existing_config

**Acceptance:**
- Plain Markdown остаётся usable без JSON migration.
- Runtime directories создаются только внутри configured documentation root/project state paths.
- Повторный init идемпотентен или явно сообщает конфликт.

## DOC02 — Register managed resource

**Implementation target:** `v0.1`
**Group / interaction:** `resources` / `command`
**Intent:** Добавить structured resource с canonical data и materialization metadata.
**CLI/API surface:** Author managed JSON under docs/_structured; inspect/discover via `docengine resources`.
**Machine CLI commands:** `resources`

**Preconditions:**
- project initialized

**Inputs:**
- managed resource JSON

**Reads:**
- resource schema registry

**Writes:**
- docs/_structured resource

**Outputs:**
- registered resource

**Side effects:**
- resource becomes discoverable

**Failure modes:**
- schema_invalid
- duplicate_resource_id
- materialization_path_escape

**Acceptance:**
- Resource проходит schema validation.
- Materialization target определён в $docengine metadata.
- Регистрация не создаёт dependency logic в JSON.

## DOC03 — Register dependency rule

**Implementation target:** `v0.1`
**Group / interaction:** `dependencies` / `command`
**Intent:** Определить code-level dependency между source и target.
**CLI/API surface:** Project code API/registry only; dependency semantics are authored in code, not persisted through a runtime registration CLI.
**Machine CLI commands:** _none_

**Preconditions:**
- target/source addressable or file path valid

**Inputs:**
- project code rule

**Reads:**
- resource/file registry

**Writes:**
- project dependency rule code/index

**Outputs:**
- registered dependency rule

**Side effects:**
- future checks track dependency

**Failure modes:**
- unknown_ref
- cyclic_dependency_disallowed
- invalid_dependency_type

**Acceptance:**
- Dependency semantics находится в code, не canonical resource data.
- Granularity/type/comparator определены.
- Rule can be inspected by graph/explain.

## DOC04 — Load structured objects

**Implementation target:** `v0.1`
**Group / interaction:** `runtime` / `query`
**Intent:** Загрузить managed structured resources как validated typed/raw objects.
**CLI/API surface:** Internal/library loader API.
**Machine CLI commands:** _none_

**Preconditions:**
- managed resources discoverable

**Inputs:**
- resource refs or scope

**Reads:**
- docs/_structured
- schemas

**Writes:**
- _none_

**Outputs:**
- immutable raw objects

**Side effects:**
- _none_

**Failure modes:**
- schema_invalid
- deserialization_error
- unknown_resource

**Acceptance:**
- Stored fields map automatically without manual per-field assignment.
- Raw object does not gain derived fields.
- Loading does not mutate source files.

## DOC05 — Build derived object

**Implementation target:** `v0.1`
**Group / interaction:** `runtime` / `command`
**Intent:** Построить новый derived object из raw/derived inputs обычным project code.
**CLI/API surface:** Builder API; runtime execution via `docengine rebuild TARGET`.
**Machine CLI commands:** `rebuild`

**Preconditions:**
- builder registered
- inputs resolvable

**Inputs:**
- target ref
- builder args

**Reads:**
- raw/derived objects via BuildContext

**Writes:**
- derived object store
- dependency receipt
- baseline slices

**Outputs:**
- derived object
- dependency receipt

**Side effects:**
- tracked reads captured

**Failure modes:**
- missing_input
- builder_error
- cycle
- write_failure

**Acceptance:**
- Raw inputs remain unchanged.
- Derived object is a new object.
- Actual dependency-aware reads are captured in receipt.
- Derived-of-derived is supported.

## DOC06 — Materialize view

**Implementation target:** `v0.1`
**Group / interaction:** `presentation` / `command`
**Intent:** Сгенерировать human/machine view из object.
**CLI/API surface:** materialize
**Machine CLI commands:** `materialize`

**Preconditions:**
- renderer registered
- target object available

**Inputs:**
- resource/target
- renderer

**Reads:**
- object
- materialization metadata

**Writes:**
- configured view path

**Outputs:**
- materialized view

**Side effects:**
- replace generated view atomically

**Failure modes:**
- renderer_error
- path_escape
- target_unavailable

**Acceptance:**
- Output path is resolved from managed resource metadata or explicit derived target config.
- Renderer performs presentation only.
- Generated output is reproducible from canonical inputs.

## DOC07 — Check dependency state

**Implementation target:** `v0.1`
**Group / interaction:** `dependencies` / `command`
**Intent:** Сравнить current dependency slices с validated baselines.
**CLI/API surface:** check
**Machine CLI commands:** `check`

**Preconditions:**
- receipts/baselines exist or target never validated

**Inputs:**
- scope

**Reads:**
- dependency receipts
- baselines
- current sources

**Writes:**
- dependency state
- events

**Outputs:**
- affected targets
- diff summaries

**Side effects:**
- mark changed targets stale/review/rebuild required

**Failure modes:**
- baseline_missing
- source_unavailable
- comparator_error

**Acceptance:**
- Only declared/captured dependency slices are compared.
- Unrelated field changes do not invalidate field-level dependencies.
- Change detection does not claim semantic incorrectness.

## DOC08 — Show project status

**Implementation target:** `v0.1`
**Group / interaction:** `operations` / `query`
**Intent:** Получить current operational state документации.
**CLI/API surface:** status
**Machine CLI commands:** `status`

**Preconditions:**
- _none_

**Inputs:**
- optional scope/filter

**Reads:**
- dependency state
- resource registry

**Writes:**
- _none_

**Outputs:**
- valid/stale/review/rebuild counts and targets

**Side effects:**
- _none_

**Failure modes:**
- state_unavailable

**Acceptance:**
- Human output and --json represent same underlying state.
- No mutation occurs.

## DOC09 — Explain target state

**Implementation target:** `v0.1`
**Group / interaction:** `operations` / `query`
**Intent:** Понять почему target stale/valid и от чего зависит.
**CLI/API surface:** explain
**Machine CLI commands:** `explain`

**Preconditions:**
- target exists

**Inputs:**
- target ref

**Reads:**
- dependency state
- receipts
- rules
- events

**Writes:**
- _none_

**Outputs:**
- explanation with upstream refs and last validation

**Side effects:**
- _none_

**Failure modes:**
- unknown_target

**Acceptance:**
- Explanation identifies exact changed dependencies and granularity.
- Includes last validated baseline/receipt identifiers.

## DOC10 — Show dependency diff

**Implementation target:** `v0.1`
**Group / interaction:** `operations` / `query`
**Intent:** Показать difference между validated dependency state и current state.
**CLI/API surface:** diff
**Machine CLI commands:** `diff`

**Preconditions:**
- target has changed dependency or baseline

**Inputs:**
- target ref

**Reads:**
- baseline slices
- current slices
- comparator

**Writes:**
- _none_

**Outputs:**
- typed diff

**Side effects:**
- _none_

**Failure modes:**
- baseline_missing
- comparator_error

**Acceptance:**
- Diff is limited to dependency slices.
- Comparator semantics are explicit.
- Whole-file Markdown dependency can produce diff without target JSON.

## DOC11 — Rebuild deterministic target

**Implementation target:** `v0.1`
**Group / interaction:** `runtime` / `command`
**Intent:** Пересобрать computational target после invalidation.
**CLI/API surface:** rebuild
**Machine CLI commands:** `rebuild`

**Preconditions:**
- builder registered
- required inputs available

**Inputs:**
- target ref

**Reads:**
- current dependencies

**Writes:**
- new derived object
- new receipt/baseline
- events
- views if requested

**Outputs:**
- rebuilt target

**Side effects:**
- replace/advance derived version

**Failure modes:**
- builder_error
- missing_input
- cycle

**Acceptance:**
- Old raw sources are not mutated.
- Successful rebuild advances baseline.
- Failure leaves previous consistent state recoverable.

## DOC12 — Review semantic dependency

**Implementation target:** `v0.1`
**Group / interaction:** `review` / `orchestration`
**Intent:** Предоставить человеку/AI всё необходимое для смысловой проверки stale target.
**CLI/API surface:** Review workflow uses `explain` + `diff`, then explicit `validate`.
**Machine CLI commands:** `explain`, `diff`, `validate`

**Preconditions:**
- target review_required

**Inputs:**
- target ref

**Reads:**
- target content
- old baseline
- current dependency slices
- diff
- rules

**Writes:**
- _none_

**Outputs:**
- review packet

**Side effects:**
- _none_

**Failure modes:**
- missing_baseline
- unknown_target

**Acceptance:**
- Packet contains target, old/current dependency state and diff.
- Engine does not decide still-valid vs needs-update.

## DOC13 — Accept current dependency state

**Implementation target:** `v0.1`
**Group / interaction:** `review` / `command`
**Intent:** Зафиксировать результат semantic review и новый validated baseline.
**CLI/API surface:** validate
**Machine CLI commands:** `validate`

**Preconditions:**
- review performed

**Inputs:**
- target ref
- result still-valid|updated
- reason
- optional evidence

**Reads:**
- current target
- current dependencies

**Writes:**
- new receipt/baseline
- dependency state
- event

**Outputs:**
- validation record

**Side effects:**
- target becomes valid on success

**Failure modes:**
- invalid_result
- target_changed_during_review
- write_failure

**Acceptance:**
- Reason is recorded.
- New baseline matches current dependencies.
- State cannot be cleared by ordinary direct state-file mutation workflow.

## DOC14 — Update stale document

**Implementation target:** `v0.1`
**Group / interaction:** `review` / `orchestration`
**Intent:** Исправить stale Markdown/managed target и перевалидировать.
**CLI/API surface:** Edit target with normal editor/AI tooling, then `validate`.
**Machine CLI commands:** `validate`

**Preconditions:**
- target stale/review_required

**Inputs:**
- target edits
- review result

**Reads:**
- diff/review packet

**Writes:**
- target content
- new baseline/receipt/event

**Outputs:**
- updated valid target

**Side effects:**
- content change plus validation

**Failure modes:**
- edit_conflict
- validation_failure

**Acceptance:**
- Updated content is validated against current dependencies.
- History preserves prior stale event/reason.

## DOC15 — Synchronize project

**Implementation target:** `v0.1`
**Group / interaction:** `operations` / `orchestration`
**Intent:** Выполнить безопасный полный рабочий цикл после изменений.
**CLI/API surface:** sync
**Machine CLI commands:** `sync`

**Preconditions:**
- _none_

**Inputs:**
- scope/options

**Reads:**
- resources
- state
- baselines
- rules

**Writes:**
- state
- rebuilt deterministic targets
- generated views
- events

**Outputs:**
- sync summary

**Side effects:**
- check + safe rebuild/materialize

**Failure modes:**
- partial_failure
- builder_error
- materialization_error

**Acceptance:**
- Deterministic affected targets rebuild automatically.
- Semantic targets remain review_required.
- Summary lists all unresolved work.

## DOC16 — Verify project

**Implementation target:** `v0.1`
**Group / interaction:** `release` / `query`
**Intent:** Проверить готовность проекта без исправления состояния.
**CLI/API surface:** verify
**Machine CLI commands:** `verify`

**Preconditions:**
- _none_

**Inputs:**
- optional strictness/profile

**Reads:**
- schemas
- state
- resources
- generated views
- receipts
- release rules

**Writes:**
- _none_

**Outputs:**
- verification report + exit code

**Side effects:**
- _none_

**Failure modes:**
- verification_failed

**Acceptance:**
- Unresolved stale/review-required can fail configured release gate.
- Generated drift is detected.
- Command is read-only.
- --json sufficient for CI/AI.

## DOC17 — Inspect history

**Implementation target:** `v0.1`
**Group / interaction:** `operations` / `query`
**Intent:** Понять chronology validation/invalidation/rebuild одного target.
**CLI/API surface:** history
**Machine CLI commands:** `history`

**Preconditions:**
- target known

**Inputs:**
- target ref

**Reads:**
- append-only events
- receipts

**Writes:**
- _none_

**Outputs:**
- ordered history

**Side effects:**
- _none_

**Failure modes:**
- unknown_target

**Acceptance:**
- History is append-only and traceable to receipts/baselines.

## DOC18 — Promote plain document

**Implementation target:** `future`
**Group / interaction:** `resources` / `command`
**Intent:** Перевести конкретный Markdown в managed structured resource постепенно.
**CLI/API surface:** Future authoring helper (`promote`), deferred beyond v0.1.
**Machine CLI commands:** _none_

**Preconditions:**
- plain document exists

**Inputs:**
- document path
- target schema/model

**Reads:**
- plain Markdown

**Writes:**
- structured resource
- materialization metadata
- possibly regenerated view

**Outputs:**
- managed resource

**Side effects:**
- document ownership changes from manual to managed

**Failure modes:**
- extraction_ambiguous
- schema_invalid
- path_conflict

**Acceptance:**
- Promotion does not require promoting unrelated Markdown.
- Canonical ownership after promotion is explicit.
- Generated Markdown parity is established.

## DOC19 — Demote managed document

**Implementation target:** `future`
**Group / interaction:** `resources` / `command`
**Intent:** Вернуть managed document к plain Markdown.
**CLI/API surface:** Future authoring helper (`demote`), deferred beyond v0.1.
**Machine CLI commands:** _none_

**Preconditions:**
- managed resource exists

**Inputs:**
- resource ref
- demotion policy

**Reads:**
- structured resource
- current materialized view
- dependencies

**Writes:**
- plain Markdown
- archived/exported structured metadata per policy

**Outputs:**
- plain document

**Side effects:**
- managed generation disabled

**Failure modes:**
- downstream_dependency_block
- export_failure

**Acceptance:**
- No downstream dependency is silently broken.
- Human-readable content remains available.
- Audit trail records ownership change.

## DOC20 — Inspect dependency graph

**Implementation target:** `v0.1`
**Group / interaction:** `dependencies` / `query`
**Intent:** Посмотреть upstream/downstream graph и affected set.
**CLI/API surface:** graph
**Machine CLI commands:** `graph`

**Preconditions:**
- _none_

**Inputs:**
- optional target/scope

**Reads:**
- dependency rules
- receipts

**Writes:**
- _none_

**Outputs:**
- graph/affected-set

**Side effects:**
- _none_

**Failure modes:**
- graph_inconsistent

**Acceptance:**
- Graph distinguishes object refs from dependency edges.
- Field/file granularity is visible.

## DOC21 — List resources

**Implementation target:** `v0.1`
**Group / interaction:** `resources` / `query`
**Intent:** Показать plain, managed and derived resources и materialization targets.
**CLI/API surface:** resources
**Machine CLI commands:** `resources`

**Preconditions:**
- _none_

**Inputs:**
- filters

**Reads:**
- documentation tree
- managed resource metadata
- derived registry

**Writes:**
- _none_

**Outputs:**
- resource inventory

**Side effects:**
- _none_

**Failure modes:**
- scan_error

**Acceptance:**
- Inventory distinguishes plain/managed/generated/derived.
- Managed outputs are shown with documentation-root-relative paths.

## DOC22 — Clean regenerate managed views

**Implementation target:** `v0.1`
**Group / interaction:** `release` / `command`
**Intent:** Пересоздать generated views из canonical inputs для parity/release.
**CLI/API surface:** `docengine materialize --all` / clean regeneration mode.
**Machine CLI commands:** `materialize`

**Preconditions:**
- canonical resources valid

**Inputs:**
- scope/all

**Reads:**
- structured/derived objects
- renderers

**Writes:**
- generated views

**Outputs:**
- clean regenerated views

**Side effects:**
- replace generated outputs

**Failure modes:**
- renderer_error
- builder_required
- path_escape

**Acceptance:**
- Generated views can be recreated after deletion.
- No manual-only state is required to reproduce them.
- Post-regeneration parity passes.
