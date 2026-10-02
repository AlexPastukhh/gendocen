# Implementation Plan — executable phase plan

Canonical detailed records: `plan/phase_records/P<n>_EXECUTION_RECORD.json`.
Acceptance axes: `plan/ACCEPTANCE_AXES.md` / `spec/registries/ACCEPTANCE_AXES.json`.
Question/answer storage rules: `plan/PHASE_EXECUTION_MODEL.md`.

Phases execute in order P0 → P8. P7 hardening occurs **before** P8 final release. DOC18/DOC19 are explicitly future use cases and are not v0.1 acceptance requirements.

## P0 — Executable foundation, contracts and test harness

**Status:** `accepted` — see `plan/P0_ACCEPTANCE_REVIEW.md` and `plan/phase_records/P0_EXECUTION_RECORD.json`.

**Scope**

- Freeze v0.1 runtime contracts from the specification.
- Create installable Python package and `docengine` entry point.
- Implement project/root discovery skeleton and stable command/JSON envelope skeleton.
- Create unit/integration/E2E test harness and sample-project fixture wiring.
- Introduce version constants for engine, persisted-state schema and machine-output schema.

**Out of scope**

- Managed resource loading semantics beyond discovery stubs.
- Dependency evaluation or materialization behavior.

**Deliverables**

- pyproject/package metadata and console entry point
- versioned machine-output envelope
- project discovery/config skeleton
- test harness with sample project
- contract-validation tests for registries/schemas

**Use cases:** DOC01

**Acceptance axes:** DAX01, DAX03, DAX04, DAX12, DAX13, DAX17, DAX19, DAX20

**Acceptance criteria**

- `P0-A1` [DAX12, DAX19] Package installs/imports and `docengine --help` executes from a clean environment.
- `P0-A2` [DAX12, DAX13] Every command can use one versioned JSON result envelope even before command-specific payloads exist.
- `P0-A3` [DAX04] Project/root discovery never writes outside configured project/documentation roots.
- `P0-A4` [DAX17] Core package imports contain no project-domain terminology or research-specific assumptions.
- `P0-A5` [DAX03, DAX19, DAX20] Specification registries/schemas parse and contract tests fail on malformed fixtures.
- `P0-A6` [DAX20] README/START_HERE accurately identify implementation status and next phase.

**Questions / decisions before implementation**

- `Q0.1` owner=`implementer` status=`answered` BLOCKING — Какую минимальную версию Python фиксируем для v0.1?
  Answer/decision: Python >= 3.11. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q0.2` owner=`implementer` status=`answered` BLOCKING — Разрешаем ли обязательные runtime-зависимости или делаем core stdlib-first?
  Answer/decision: Stdlib-first core; allow small explicit dependencies only when they materially reduce correctness risk (initial candidate: jsonschema). / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q0.3` owner=`implementer` status=`answered` BLOCKING — Какой основной способ установки/запуска считаем canonical?
  Answer/decision: pyproject package + console script `docengine`; editable install for development, wheel for distribution. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Full record: `plan/phase_records/P0_EXECUTION_RECORD.json`.

## P1 — Project, resource, storage and loader core

**Status:** `accepted` — see `plan/P1_ACCEPTANCE_REVIEW.md`, `plan/P1_AXIS_AUDIT.md` and `plan/phase_records/P1_EXECUTION_RECORD.json`.

**Scope**

- Implement documentation-root/project discovery and configuration.
- Discover plain Markdown and managed structured resources.
- Implement `$docengine` envelope parsing, schema validation and resource identity.
- Implement ResourceRef/FieldRef parsing and resolver.
- Implement immutable generic structured objects and adapters.
- Enforce mirrored `_structured/` convention and materialization path confinement.

**Out of scope**

- Derived builders.
- Baselines and dependency state.

**Deliverables**

- project config contract
- resource catalog
- ResourceRef/FieldRef implementation
- managed resource loader
- schema-validation adapter
- immutable object representation
- resources CLI/query payload

**Use cases:** DOC01, DOC02, DOC04, DOC21

**Acceptance axes:** DAX01, DAX02, DAX03, DAX04, DAX05, DAX12, DAX17, DAX19, DAX20

**Acceptance criteria**

- `P1-A1` [DAX01, DAX02] Plain Markdown works without JSON sidecars and is not silently promoted to managed form.
- `P1-A2` [DAX03, DAX17] Managed JSON under documentation root validates and loads without project code manually mapping every field.
- `P1-A3` [DAX02, DAX04] `$docengine.materialize[].path` resolves relative to documentation root and traversal outside root is rejected.
- `P1-A4` [DAX03] ResourceRef/FieldRef round-trip parsing is stable and malformed/ambiguous refs fail clearly.
- `P1-A5` [DAX05] Loaded raw objects are immutable through engine APIs.
- `P1-A6` [DAX12, DAX19] Sample project resource inventory is deterministic in both human and JSON output.

**Questions / decisions before implementation**

- `Q1.1` owner=`implementer` status=`answered` BLOCKING — Как engine находит project/documentation root при запуске?
  Answer/decision: Priority: explicit `--project-root`/`--docs-root` > project config > upward search from cwd; never guess across filesystem boundaries. / Adopt safe deterministic root discovery with strict path confinement.
- `Q1.2` owner=`implementer` status=`answered` BLOCKING — Где хранить project-level config и как его назвать?
  Answer/decision: `docengine.toml` в project root; documentation-owned structured/runtime data остаётся under docs. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q1.3` owner=`implementer` status=`answered` BLOCKING — Каким будет базовый runtime object representation для произвольных JSON schemas?
  Answer/decision: Immutable generic mapping/object wrapper with field/path access; optional project adapters/dataclasses may layer on top. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q1.4` owner=`implementer` status=`answered` BLOCKING — Фиксируем ли exact ResourceRef syntax уже в P1?
  Answer/decision: Yes: `resource://<namespace>/<id>#/<json-pointer>` for structured resources and `file://<docs-relative-path>` for files; escaping follows URI + JSON Pointer rules. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Full record: `plan/phase_records/P1_EXECUTION_RECORD.json`.

## P2 — Builders, derived objects and tracked reads

**Status:** accepted after independent re-audit

**Scope**

- Implement builder registry and BuildContext.
- Allow project code to create new derived objects from raw and/or derived inputs.
- Capture actual dependency-aware reads at field/resource granularity.
- Support derived-of-derived chains and deterministic cycle detection.
- Keep pure business functions separate from dependency infrastructure.

**Out of scope**

- Persisted baselines/diff/state.
- Semantic review decisions.

**Deliverables**

- builder registry/API
- BuildContext
- derived object envelope/provenance metadata
- tracked-read capture
- cycle detection
- synthetic non-documentation fixture

**Use cases:** DOC03, DOC05

**Acceptance axes:** DAX02, DAX03, DAX04, DAX05, DAX06, DAX10, DAX14, DAX17, DAX19, DAX20

**Acceptance criteria**

- `P2-A1` [DAX05] Builder returns a new derived object; raw input values/objects remain unchanged.
- `P2-A2` [DAX06] Only fields/resources actually read through tracked APIs appear in captured dependency evidence.
- `P2-A3` [DAX10] raw+raw, raw+derived and derived+derived chains execute reproducibly.
- `P2-A4` [DAX06, DAX14] Dependency cycles are detected deterministically with an explainable path, not recursion failure.
- `P2-A5` [DAX17] A synthetic unrelated domain (e.g. product+tax) uses the same runtime without research/document-specific core changes.
- `P2-A6` [DAX10, DAX19] Repeated deterministic build with unchanged inputs produces equivalent output/provenance.
- `P2-A7` [DAX02, DAX03, DAX04, DAX17] Project-specific builder code is loaded only from the configured confined project package outside documentation root, and materialized derived targets require documentation-owned derived descriptors.
- `P2-A8` [DAX03, DAX20] Derived-object/provenance envelope, documentation, active wheel and transferable package agree with the implemented P2 runtime contract.

**Questions / decisions before implementation**

- `Q2.1` owner=`implementer` status=`answered` BLOCKING — Как project-specific code подключается в v0.1?
  Answer/decision: Importable local `docengine_project` package configured in `docengine.toml`; Python entry-point plugins may be added later. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q2.2` owner=`implementer` status=`answered` BLOCKING — Как регистрировать builders: decorators, explicit registry или оба?
  Answer/decision: Explicit registry as canonical mechanism with decorator convenience that writes into it. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q2.3` owner=`implementer` status=`answered` BLOCKING — Разрешать ли builder читать filesystem/JSON напрямую в обход context?
  Answer/decision: No for tracked inputs: project builder may call pure helpers, but dependency-bearing reads must go through context/resolver; escape hatch must be explicit and unaudited. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q2.4` owner=`implementer` status=`answered` BLOCKING — Что делать с dependency cycles?
  Answer/decision: Treat as configuration/build error in v0.1; report exact cycle path. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Whole-resource dependency versions use canonical domain `data`; physical JSON `source_hash` is separate source provenance.

Full record: `plan/phase_records/P2_EXECUTION_RECORD.json`.

## P3 — Dependency receipts, baselines, comparators, diff and state

**Scope**

- Persist DependencyReceipt from tracked reads/explicit rules.
- Store validated dependency slices, not unrelated upstream content.
- Implement comparator registry and typed diffs.
- Implement dependency graph/reverse affected-set lookup.
- Implement current dependency state and append-only events.
- Detect upstream change and mark affected targets stale/build-required/review-required according to dependency mode.

**Out of scope**

- Human/AI semantic acceptance workflow beyond state generation.
- Renderer/materialization rebuilds.

**Deliverables**

- receipt store
- baseline store
- comparator registry
- diff model
- state store
- event log
- check/diff/explain/graph core

**Use cases:** DOC07, DOC08, DOC09, DOC10, DOC17, DOC20

**Acceptance axes:** DAX01, DAX03, DAX05, DAX06, DAX07, DAX08, DAX10, DAX14, DAX19

**Acceptance criteria**

- `P3-A1` [DAX06, DAX07] Field-level dependency snapshots contain only the referenced field slice; unrelated field changes do not invalidate target.
- `P3-A2` [DAX01, DAX06] Whole-file Markdown dependency works without introducing JSON for the target/source merely to track the file.
- `P3-A3` [DAX07, DAX10] Diff shows validated baseline versus current state using the declared comparator and is stable across retries.
- `P3-A4` [DAX08] Dependency change updates runtime state but does not modify canonical source content or assert semantic falsity.
- `P3-A5` [DAX06, DAX19] Reverse graph identifies exactly affected targets for a changed dependency.
- `P3-A6` [DAX14, DAX19] Receipts, state and append-only events are mutually explainable and inconsistent fixtures are detected.
- `P3-A7` [DAX03, DAX05, DAX08, DAX10] Changing project builder/helper source revision with unchanged data dependencies is detected as a derivation change, recorded in evidence/history and makes affected deterministic targets `build_required` until rebuilt.

**Questions / decisions before implementation**

- `Q3.1` owner=`implementer` status=`answered` BLOCKING — Как хранить baseline snapshots: per-target files или content-addressed blobs?
  Answer/decision: Content-addressed normalized blobs referenced by receipts; target history lives in receipts/events. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q3.2` owner=`implementer` status=`answered` BLOCKING — Какие comparators обязательны в v0.1?
  Answer/decision: `exact`, `json_structured`, `sequence`, `set`, `text_unified`; Markdown AST/semantic comparator deferred. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q3.3` owner=`user` status=`answered` BLOCKING — Должен ли `check` изменять dependency state?
  Answer/decision: Проверка зависимостей должна при обнаружении изменения сразу отражать stale/review состояние; semantic validity затем проверяет пользователь/AI. / `check` обновляет runtime dependency state/events, но не canonical content и не validated baseline.
- `Q3.4` owner=`implementer` status=`answered` BLOCKING — Какие status значения считаем каноническими?
  Answer/decision: At least `valid`, `stale`, `build_required`, `review_required`, `invalid`; `stale` may be umbrella in human text but machine state uses the more specific state when known. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q3.5` owner=`implementer` status=`answered` BLOCKING — Нормализуем ли Markdown перед baseline/hash в v0.1?
  Answer/decision: Use raw UTF-8 normalized line endings for v0.1 text comparator; add AST-aware comparator later. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q3.6` owner=`implementer` status=`answered` BLOCKING — Как P3 должен учитывать изменение builder/helper code при неизменных data dependencies?
  Answer/decision: Persist P2 `builder_revision` in builder receipts/state and compare it during `check`; revision change produces `build_required` for deterministic targets. / Treat builder source revision as a first-class invalidation input.

Full record: `plan/phase_records/P3_EXECUTION_RECORD.json`.

## P4 — Semantic dependencies and review workflow

**Status:** accepted

**Scope**

- Implement explicit semantic dependency rule registration.
- Expose review context: target, old baseline, current dependency slices, typed diff and history.
- Implement `validate still-valid|updated` mutation with reason/evidence.
- Advance baselines only after explicit review outcome.
- Preserve old receipts/events for audit.

**Out of scope**

- Automated LLM semantic judgment inside engine.
- Fine-grained Markdown section targeting unless explicitly chosen.

**Deliverables**

- semantic dependency registry
- ValidationContext/review payload
- validate command core
- review event types
- baseline advancement rules

**Use cases:** DOC03, DOC12, DOC13, DOC14

**Acceptance axes:** DAX01, DAX02, DAX03, DAX04, DAX05, DAX06, DAX07, DAX08, DAX09, DAX10, DAX12, DAX13, DAX14, DAX16, DAX17, DAX19, DAX20

**Acceptance criteria**

- `P4-A1` [DAX08, DAX09] Changing semantic dependency makes target review_required without engine claiming target content is wrong.
- `P4-A2` [DAX09, DAX13] AI/human review receives old/current dependency slices, diff, target identity and prior validation context.
- `P4-A3` [DAX09, DAX10] `still-valid` advances baseline without altering target content; `updated` requires current target state and records decision/reason.
- `P4-A4` [DAX09, DAX14] Direct edit of dependency_state cannot serve as normal acceptance path; official validation mutation records history.
- `P4-A5` [DAX14] Old validation events/receipts remain inspectable after baseline advancement.
- `P4-A6` [DAX10, DAX19] Validation is idempotent for the same target/current dependency state/decision or explicitly detects duplicate intent.
- `P4-A7` [DAX02, DAX06, DAX17] Semantic rules are code-owned, graph/explain inspectable and cannot silently replace a deterministic receipt on the same exact target.
- `P4-A8` [DAX03, DAX10, DAX14, DAX16] Validation is bound to the reviewed context token and P4 persisted additions remain backward-readable with P3 evidence.
- `P4-A9` [DAX12, DAX13, DAX20] Semantic validation has machine-readable error/result contracts plus reason/actor/evidence trail and synchronized handoff docs/package identity.

**Questions / decisions before implementation**

- `Q4.1` owner=`implementer` status=`answered` BLOCKING — Делаем ли `--reason` обязательным для semantic validation?
  Answer/decision: Yes. Non-empty `--reason` is required for explicit semantic `still-valid` and `updated` decisions. / Require a review reason so semantic acceptance remains portable and auditable.
- `Q4.2` owner=`implementer` status=`answered` BLOCKING — Нужен ли ручной `force-valid` обход review в v0.1?
  Answer/decision: No normal force-valid path in v0.1; recovery/admin repair must be a separate explicit future capability. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q4.3` owner=`user` status=`answered` non-blocking — Поддерживаем ли dependency target на конкретную Markdown section в v0.1?
  Answer/decision: No. Markdown dependencies in v0.1 target the whole file. If dependency granularity must be narrower, move that content into structured JSON and address the structured field/object.
- `Q4.4` owner=`implementer` status=`answered` BLOCKING — Нужно ли хранить actor metadata для review?
  Answer/decision: Store `actor_kind` = human|ai|ci|unknown and optional free-form non-sensitive actor label; no identity required. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Full record: `plan/phase_records/P4_EXECUTION_RECORD.json`.

## P5 — Renderers, materialization, drift detection and sync

**Status:** accepted

**Scope**

- Implement renderer registry and Markdown renderer contract.
- Resolve materialization targets from `$docengine.materialize[]`.
- Implement affected-only materialization and full clean regeneration.
- Detect generated-view drift.
- Implement `sync` orchestration: check, deterministic rebuild, materialize, leave semantic review unresolved.

**Out of scope**

- Release packaging/verify policy beyond primitives.
- Background daemon/watch as canonical workflow.

**Deliverables**

- renderer registry
- materialization planner/runner
- generated-output provenance/digest
- drift detector
- sync orchestration

**Use cases:** DOC06, DOC11, DOC15, DOC22

**Acceptance axes:** DAX02, DAX03, DAX04, DAX06, DAX08, DAX09, DAX10, DAX11, DAX12, DAX13, DAX14, DAX17, DAX19, DAX20

**Acceptance criteria**

- `P5-A1` [DAX11] Managed Markdown can be deleted and deterministically recreated from canonical structured/derived state.
- `P5-A2` [DAX02, DAX04] Materialization never escapes documentation root and never overwrites plain/canonical files not owned by a materialization target.
- `P5-A3` [DAX06, DAX10, DAX11] Affected-only sync rebuilds/materializes only deterministic targets reachable from changed dependencies.
- `P5-A4` [DAX09, DAX12] Semantic targets remain review_required; sync does not fabricate semantic acceptance.
- `P5-A5` [DAX11] Manual drift in generated Markdown is detected; clean full regeneration restores canonical view.
- `P5-A6` [DAX10, DAX19] Repeated sync with no changes is idempotent and produces no spurious events/output churn.
- `P5-A7` [DAX03, DAX11, DAX14] Materialization state records owner, renderer/revision, input revision and output digest in a versioned persisted contract.
- `P5-A8` [DAX12, DAX13] `rebuild`, `materialize` and `sync` expose machine-readable operational results, including `attention_required` without semantic auto-acceptance.
- `P5-A9` [DAX17] The same core supports unrelated product/tax documentation and project-defined renderers without domain changes.
- `P5-A10` [DAX20] P5 handoff docs, schemas, wheel/source parity and transferable package identity agree with the accepted runtime.

**Questions / decisions before implementation**

- `Q5.1` owner=`implementer` status=`answered` BLOCKING — Как определять ownership/drift generated Markdown: marker в файле или digest в runtime state?
  Answer/decision: Use explicit materialization registration + stored output digest/provenance; do not require visible marker in document content by default. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q5.2` owner=`implementer` status=`answered` BLOCKING — Какой режим `sync` default: affected-only или full materialize?
  Answer/decision: Affected-only by default; `--all`/clean mode for explicit full regeneration. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q5.3` owner=`implementer` status=`answered` BLOCKING — Что возвращает `sync`, если deterministic work успешен, но остались semantic `review_required`?
  Answer/decision: Command completes successfully as an operation but machine result reports `attention_required`; reserve a documented distinct exit code for unresolved review when desired by automation. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q5.4` owner=`user` status=`answered` BLOCKING — Нужен ли filesystem watch/daemon в первой рабочей версии?
  Answer/decision: Основная модель — обычная запускаемая программа с командами; background watch не должен быть обязательным механизмом. / Explicit CLI/sync canonical; watch optional/deferred.

**Emergent decisions during implementation**

- `Q5.E1` owner=`implementer` status=`answered` non-blocking — Mixed semantic↔deterministic SCC uses bounded sync: deterministic members run at most once per occurrence; semantic members remain unresolved; affected mixed SCC returns `attention_required`; pure deterministic cycles remain errors.
- `Q5.E2` owner=`implementer` status=`answered` non-blocking — Removed/renamed materialization targets are preserved and reported as orphaned attention work; no destructive auto-delete in v0.1.
- `Q5.E3` owner=`implementer` status=`answered` non-blocking — Orphan attention is resolved explicitly with provenance-preserving `materialize file://PATH --ack-orphan`; no file/provenance deletion.
- `Q5.E4` owner=`implementer` status=`answered` non-blocking — P3/P4 diagnostics do not depend on P5 renderer registration; renderer loading is component-scoped.

Full record: `plan/phase_records/P5_EXECUTION_RECORD.json`.

## P6 — Complete CLI and AI/CI operating protocol

**Status:** accepted

**Scope**

- Wire status/check/diff/explain/sync/rebuild/validate/materialize/verify/history/graph/resources to implemented services.
- Freeze machine-readable command envelope and error model.
- Freeze exit-code policy and mutation/query boundaries.
- Demonstrate clean handoff workflow in a fresh process/chat-like environment.

**Out of scope**

- Release archive signing/distribution.
- Concurrency hardening beyond current safe assumptions.

**Deliverables**

- complete CLI command set
- versioned JSON output schema
- exit-code table
- AI operating runbook
- E2E command fixtures

**Use cases:** DOC07, DOC08, DOC09, DOC10, DOC11, DOC12, DOC13, DOC15, DOC16, DOC17, DOC20, DOC21, DOC01

**Acceptance axes:** DAX03, DAX09, DAX11, DAX12, DAX13, DAX14, DAX16, DAX19, DAX20

**Acceptance criteria**

- `P6-A1` [DAX12, DAX13] Every canonical command has human and `--json` output with the same underlying facts.
- `P6-A2` [DAX12, DAX13] Machine envelope/error schema is versioned and stable across success, attention-required and failure cases.
- `P6-A3` [DAX12, DAX19] Query commands do not mutate state; command/orchestration mutations are explicitly documented and tested.
- `P6-A4` [DAX13] A fresh AI-style consumer can inspect status, understand stale cause/diff, perform allowed action and reach verify without opening internal state files.
- `P6-A5` [DAX14] History/explain output contains sufficient receipt/baseline/event references for audit.
- `P6-A6` [DAX20] CLI documentation and registries match implemented flags/exit codes exactly.
- `P6-A7` [DAX09, DAX11, DAX12, DAX13, DAX14] `verify` is read-only, complete-report, and fails blocking release findings without crashing or auto-fixing.
- `P6-A8` [DAX03, DAX12, DAX13, DAX16] Machine envelope incompatibility is explicit via schema-version bump and all JSON-requested usage/internal failures stay enveloped.

**Questions / decisions before implementation**

- `Q6.1` owner=`implementer` status=`answered` BLOCKING — Как выглядит canonical JSON envelope для всех CLI команд?
  Answer/decision: Top-level: `schema_version`, `command`, `ok`, `attention_required`, `data`, `warnings`, `errors`, `meta`. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q6.2` owner=`implementer` status=`answered` BLOCKING — Фиксируем ли единый набор exit codes?
  Answer/decision: Yes. Recommended: 0 success/no blocking attention; 2 completed but attention/review required; 3 verification/domain validation failure; 4 usage/config error; 5 internal/runtime failure. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q6.3` owner=`implementer` status=`answered` BLOCKING — Какие команды строго read-only?
  Answer/decision: `status`, `diff`, `explain`, `history`, `graph`, `resources`, and `verify` are read-only; `check`, `sync`, `rebuild`, `validate`, `materialize`, and `init` may mutate only the state/output documented for each command. / Freeze query/mutation boundaries in CLI contract and test them.
- `Q6.4` owner=`implementer` status=`answered` BLOCKING — Нужно ли поддерживать stdin/stdout-only режим для агента?
  Answer/decision: JSON stdout is mandatory; structured stdin for bulk actions deferred unless a concrete use case appears. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Full record: `plan/phase_records/P6_EXECUTION_RECORD.json`.

## P7 — Hardening, recovery, migrations and scalability

**Status:** accepted — final dev15 package gate passed; P7-CG1 carried historical P7-A5/DAX18 partial to P8-A8, which subsequently resolved it.

**Scope**

- Add single-writer locking/transactional multi-file updates.
- Implement crash recovery/reconciliation for state/receipt/baseline/event operations.
- Implement migration framework for persisted schemas.
- Benchmark and optimize dependency graph/diff/materialization on synthetic large projects.
- Evaluate optional watch mode only after explicit-command semantics are stable.

**Out of scope**

- Distributed multi-writer database service.
- LLM semantic reviewer embedded into engine core.
- Final release packaging/handoff (P8).

**Deliverables**

- lock/transaction layer
- recovery/reconcile command or startup repair
- migration registry/fixtures
- benchmark suite/performance budget
- optional watch-mode decision

**Use cases:** DOC15, DOC16, DOC17, DOC20

**Acceptance axes:** DAX14, DAX15, DAX16, DAX18, DAX19, DAX20

**Acceptance criteria**

- `P7-A1` [DAX15, DAX19] Crash-injection tests do not leave contradictory state/receipt/baseline/event combinations.
- `P7-A2` [DAX15] Concurrent writers are serialized or rejected clearly; readers do not observe partially committed state.
- `P7-A3` [DAX16] Migration fixtures preserve or explicitly transform receipts/baselines/history with version checks.
- `P7-A4` [DAX14, DAX15] Recovery can diagnose and reconcile interrupted operations with an auditable event.
- `P7-A5` [DAX18] Declared synthetic scale benchmark meets the recorded performance budget or phase remains partial.
- `P7-A6` [DAX16, DAX20] Hardening changes do not alter user-visible semantics from accepted earlier phases without corresponding contract/migration updates.

**Questions / decisions before implementation**

- `Q7.1` owner=`implementer` status=`answered` BLOCKING — Какую concurrency model фиксируем для первого hardened release?
  Answer/decision: Single writer per documentation root via lock; concurrent read-only commands allowed when safe. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q7.2` owner=`implementer` status=`answered` BLOCKING — Когда обязательна migration, а когда допустим reset runtime state?
  Answer/decision: Canonical/document data never reset. Persisted dependency state formats require migrations once released; reset allowed only for explicitly disposable caches, not receipts/history/baselines. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q7.3` owner=`implementer` status=`answered` non-blocking — Какой synthetic scale и performance budget принять?
  Answer/decision: Start benchmark fixture at 10k resources / 50k dependency edges; establish measured baseline in P8, then record an environment-normalized budget before acceptance. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q7.4` owner=`implementer` status=`answered` non-blocking — Нужен ли watch mode вообще в v0.x?
  Answer/decision: Keep optional and out of acceptance unless explicit-command workflow proves insufficient. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

**Emergent decision**

- `Q7.E8` owner=`implementer` status=`answered` BLOCKING — P7-A5 requires a budget or partial phase, while Q7.3 defers the normalized budget to P8 and the phase schema has no `partial` status. Decision: accept the completed P7 hardening scope with DAX18 explicitly partial; carry DAX18 into P8 as a blocking release-gate axis. P8-A8 must set a normalized budget and pass the declared benchmark before P8 acceptance.

Full record: `plan/phase_records/P7_EXECUTION_RECORD.json`.


**Post-acceptance P7 decisions**

- `Q7.E9` owner=`implementer` status=`answered` BLOCKING — corrupt/semantically impossible journals fail closed before any recovery mutation.
- `Q7.E10` owner=`implementer` status=`answered` BLOCKING — migrated runtime provenance is registry-bound; unsafe/corrupt released evidence is never silently migrated.
- `Q7.E11` owner=`implementer` status=`answered` non-blocking — recovery/migration audit logs are verification evidence and corruption is a blocking complete-report finding.

## P8 — Final verification, release gate, portability and handoff

**Status:** accepted

**Scope**

- Run after P7 hardening phase acceptance; historical P7-A5/DAX18 partial is carried explicitly by P7-CG1 and must be closed by P8-A8 before final release. P8 subsequently resolved this gate.
- Implement strict read-only verify over schemas, state, dependencies, generated parity and unresolved review.
- Implement package/project manifest integrity checks.
- Run full lifecycle on sample project from a clean checkout/archive.
- Create release/handoff artifacts and updated system map.
- Prove domain independence with at least one non-documentation fixture.

**Out of scope**

- State migrations beyond current version unless schema changed during P0-P7.
- Large-scale concurrency/performance hardening.

**Deliverables**

- verify gate
- manifest validator
- clean-regeneration release check
- portable archive/wheel
- handoff checklist
- acceptance report

**Use cases:** DOC16, DOC22

**Acceptance axes:** DAX01, DAX02, DAX03, DAX04, DAX05, DAX06, DAX07, DAX08, DAX09, DAX10, DAX11, DAX12, DAX13, DAX15, DAX17, DAX18, DAX19, DAX20

**Acceptance criteria**

- `P8-A1` [DAX11, DAX12] Verify is read-only and always emits a complete report; blocking findings produce `ok=false` plus non-zero exit code rather than an execution crash.
- `P8-A2` [DAX13, DAX17, DAX20] Clean archive install + sample lifecycle succeeds without hidden local paths/state.
- `P8-A3` [DAX20] Manifest detects missing/changed tracked files and is regenerated only through release tooling.
- `P8-A4` [DAX20] System map, README, CLI registry, schemas and use-case registry describe actual implementation.
- `P8-A5` [DAX17] Non-documentation synthetic fixture passes core build/dependency workflow without core modifications.
- `P8-A6` [DAX19, DAX20] All prior phase acceptance records contain evidence and no unresolved blocking question remains for accepted phases.
- `P8-A7` [DAX01, DAX02, DAX03, DAX04, DAX05, DAX06, DAX07, DAX08, DAX09, DAX10, DAX11, DAX12, DAX13, DAX15, DAX17, DAX18, DAX19, DAX20] Final release review records pass/not_applicable with evidence for every release-gate DAX axis, including DAX15 completed in P7 and DAX18 closed from the P7 baseline, and no accepted phase has an unresolved blocking question.
- `P8-A8` [DAX18] Establish and record an environment-normalized budget for the declared P7 10k/50k + 10k diff/render benchmark, rerun it in the release environment, and block P8 acceptance unless the benchmark passes.

**Questions / decisions before implementation**

- `Q8.1` owner=`user` status=`answered` BLOCKING — Должен ли release verify разрешать `review_required` по умолчанию?
  Answer/decision: No. `verify` always emits a complete report; unresolved `review_required` is a blocking verification result with `ok=false` and non-zero exit code, not an execution crash. / Use this as the default release verification policy.
- `Q8.2` owner=`implementer` status=`answered` BLOCKING — Какой артефакт передачи считаем основным: wheel, source archive или оба?
  Answer/decision: Both: source archive containing docs/examples/tests + buildable wheel; source archive is canonical handoff artifact. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q8.3` owner=`implementer` status=`answered` BLOCKING — Что входит в engine release manifest, а что считается volatile project runtime state?
  Answer/decision: Engine manifest tracks package/spec/examples/tests. Project runtime state is verified by project-level commands and not embedded as engine release integrity state. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.
- `Q8.4` owner=`implementer` status=`answered` BLOCKING — Нужна ли compatibility guarantee до 1.0?
  Answer/decision: Persisted formats are explicitly versioned from v0.1; breaking changes allowed pre-1.0 only with migration or clear reset path documented and tested. / Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

Full record: `plan/phase_records/P8_EXECUTION_RECORD.json`.


## P3 pre-execution clarifications surfaced by P2 independent re-audit

- **Q3.7 (answered, implementer):** whole `resource://...` baseline means the complete domain `data` value, not unrelated `$docengine` materialization/ownership metadata.
- **Q3.8 (answered, implementer):** v0.1 code-revision invalidation is conservatively package-wide; finer per-builder/helper revision tracking is deferred unless rebuild noise proves material.

Canonical details remain in `plan/phase_records/P3_EXECUTION_RECORD.json`.
