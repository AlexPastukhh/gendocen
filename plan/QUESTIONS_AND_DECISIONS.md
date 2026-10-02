# Questions and Decisions

Generated human view from canonical `plan/phase_records/P*_EXECUTION_RECORD.json`. Canonical ownership remains the JSON phase records.

## P0 — Executable foundation, contracts and test harness

### Q0.1 — owner: `implementer` [BLOCKING]
**Question:** Какую минимальную версию Python фиксируем для v0.1?
**Status:** answered
**Answer:** Python >= 3.11.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q0.2 — owner: `implementer` [BLOCKING]
**Question:** Разрешаем ли обязательные runtime-зависимости или делаем core stdlib-first?
**Status:** answered
**Answer:** Stdlib-first core; allow small explicit dependencies only when they materially reduce correctness risk (initial candidate: jsonschema).
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q0.3 — owner: `implementer` [BLOCKING]
**Question:** Какой основной способ установки/запуска считаем canonical?
**Status:** answered
**Answer:** pyproject package + console script `docengine`; editable install for development, wheel for distribution.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q0.E1 — owner: `implementer` [non-blocking]
**Question:** Как проверять clean-environment installation offline, если новый Python venv не содержит setuptools/build backend?
**Status:** answered
**Answer:** Clean-environment acceptance installs the prebuilt wheel; source/editable install remains a development workflow that requires build tooling.
**Decision:** Canonical distribution verification uses a prebuilt wheel. The runtime remains dependency-free in P0; build tooling is not made a runtime dependency.

### Q0.E2 — owner: `implementer` [non-blocking]
**Question:** Что означает PASS по DAX-оси внутри раннего phase: глобальное закрытие оси или только проверка применимого phase risk slice?
**Status:** answered
**Answer:** Использовать phase-local PASS и отдельно считать global progress; P8 выполняет consolidated global review.
**Decision:** Уточнить acceptance model и human docs; P0 axis statuses остаются PASS только в phase scope.

### Q0.E3 — owner: `implementer` [non-blocking]
**Question:** Должен ли manifest/spec audit считать transient Python/pytest artifacts частью canonical package?
**Status:** answered
**Answer:** Игнорировать `.pytest_cache`, `__pycache__`, `*.pyc`, `*.pyo`, `.coverage` и `*.egg-info` при manifest file-set check.
**Decision:** Исправить `tools/audit_spec.py` и добавить regression test, который запускает audit при наличии transient artifacts.

## P1 — Project, resource, storage and loader core

### Q1.1 — owner: `implementer` [BLOCKING]
**Question:** Как engine находит project/documentation root при запуске?
**Status:** answered
**Answer:** Priority: explicit `--project-root`/`--docs-root` > project config > upward search from cwd; never guess across filesystem boundaries.
**Decision:** Adopt safe deterministic root discovery with strict path confinement.

### Q1.2 — owner: `implementer` [BLOCKING]
**Question:** Где хранить project-level config и как его назвать?
**Status:** answered
**Answer:** `docengine.toml` в project root; documentation-owned structured/runtime data остаётся under docs.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q1.3 — owner: `implementer` [BLOCKING]
**Question:** Каким будет базовый runtime object representation для произвольных JSON schemas?
**Status:** answered
**Answer:** Immutable generic mapping/object wrapper with field/path access; optional project adapters/dataclasses may layer on top.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q1.4 — owner: `implementer` [BLOCKING]
**Question:** Фиксируем ли exact ResourceRef syntax уже в P1?
**Status:** answered
**Answer:** Yes: `resource://<namespace>/<id>#/<json-pointer>` for structured resources and `file://<docs-relative-path>` for files; escaping follows URI + JSON Pointer rules.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q1.E1 — owner: `implementer` [BLOCKING]
**Question:** Как разрешить обнаруженное расхождение между старыми docs-примерами `resource://policies.method_policy` и уже принятым Q1.4 форматом `resource://<namespace>/<id>`?
**Status:** answered
**Answer:** Использовать `resource://<namespace>/<id>#/<json-pointer>`; dotted resource_id отображается как namespace + local id.
**Decision:** Старые dot-form URI examples исправлены; canonical parser/formatter реализован и malformed/ambiguous refs rejected.

### Q1.E2 — owner: `implementer` [BLOCKING]
**Question:** Нужна ли обязательная runtime dependency на полный `jsonschema` validator уже в P1?
**Status:** answered
**Answer:** Обязательную dependency не добавлять в P1; реализовать `SchemaValidator` boundary и `CoreSchemaValidator` с explicit supported subset.
**Decision:** P1 runtime остаётся dependency-free; unknown schema URI, malformed schema и unsupported semantic keyword дают явную ошибку.

### Q1.E3 — owner: `implementer` [BLOCKING]
**Question:** `docs/_structured/` mirror — только рекомендация или runtime invariant для Markdown materialization в v0.1?
**Status:** answered
**Answer:** Enforce mirror rule for Markdown materialization in v0.1.
**Decision:** `_structured/a/b.json` с Markdown output обязан владеть `a/b.md`; mismatch is ResourceError.

### Q1.E4 — owner: `implementer` [BLOCKING]
**Question:** Должен ли P1 distribution иметь новую runtime build version относительно P0?
**Status:** answered
**Answer:** Да; P1 wheel/version = `0.1.0.dev1`.
**Decision:** `pyproject.toml` и `ENGINE_VERSION` синхронно обновлены до `0.1.0.dev1`; persisted/machine schema versions не изменены.

### Q1.E5 — owner: `implementer` [BLOCKING]
**Question:** Как P1 должен обращаться с symlink/path edge cases для config, structured sources и Markdown inventory?
**Status:** answered
**Answer:** Следовать real-path confinement; `docengine.toml` symlink не использовать для v0.1 initialization/config loading.
**Decision:** Добавлены checks и regression tests для dangling config symlink, docs symlink outside, structured-dir escape и plain Markdown symlink escape.

### Q1.E6 — owner: `implementer` [non-blocking]
**Question:** Должен ли source-package test extra явно включать pytest, если canonical reproduction command использует `python -m pytest`?
**Status:** answered
**Answer:** Да; `pytest>=8,<9` добавлен в optional test dependencies рядом с jsonschema.
**Decision:** Runtime dependency list остаётся пустым; wheel metadata содержит pytest/jsonschema только под extra `test`.

### Q1.E7 — owner: `implementer` [BLOCKING]
**Question:** Как upward discovery должен трактовать dangling/non-file `docengine.toml` marker в родительском каталоге?
**Status:** answered
**Answer:** Лексическое наличие marker теперь останавливает search даже для dangling symlink/не-файла.
**Decision:** `_find_project_root` использует marker presence, а не только `is_file()`; malformed marker приводит к явной ошибке, не к silent fallback.

### Q1.E8 — owner: `implementer` [BLOCKING]
**Question:** Могут ли `structured_dir` и `dependency_dir` совпадать/пересекаться, и могут ли materialization outputs писать внутрь этих reserved trees?
**Status:** answered
**Answer:** Нет: reserved trees должны быть disjoint, dedicated subtrees, а generated output не может их таргетировать.
**Decision:** Config validation rejects equal/ancestor overlap/`.`; materialization validation rejects targets under structured/dependency roots for every renderer.

### Q1.E9 — owner: `implementer` [BLOCKING]
**Question:** Должен ли strict JSON loader отклонять numeric literals, которые Python преобразует в `inf` из-за overflow (например `1e999`)?
**Status:** answered
**Answer:** Да; overflow-to-infinity запрещён так же, как NaN/Infinity literals.
**Decision:** Добавлен strict `parse_float` finite check и regression tests.

### Q1.E10 — owner: `implementer` [BLOCKING]
**Question:** Должен ли active `dist/` содержать исторические wheels вместе с текущим?
**Status:** answered
**Answer:** Нет. Active dist должен содержать ровно текущую distribution.
**Decision:** P0/P1 historical wheels перенесены в `plan/evidence/<phase>/artifacts/`; spec audit проверяет exactly-one current wheel + version/metadata identity. Runtime build bumped to 0.1.0.dev2.

### Q1.E11 — owner: `implementer` [BLOCKING]
**Question:** Должен ли DAX20 быть mapped axis P1, если каждый phase выпускает новый manifest/wheel/README/transferable archive?
**Status:** answered
**Answer:** Да; P1 materially changes distribution/handoff and therefore maps DAX20.
**Decision:** DAX20 добавлен в P1.acceptance_axes и axis_reviews; P8 всё равно выполняет global consolidated closure.

### Q1.E12 — owner: `implementer` [BLOCKING]
**Question:** Должен ли передаваемый source checkout запускать canonical test suite без ручного PYTHONPATH или предварительной установки package?
**Status:** answered
**Answer:** Да. Source checkout должен быть self-contained для запуска тестов.
**Decision:** Добавлен `[tool.pytest.ini_options] pythonpath=["src"]`; README/START_HERE используют bare `python -m pytest -q`; regression test фиксирует contract.

## P2 — Builders, derived objects and tracked reads

### Q2.1 — owner: `implementer` [BLOCKING]
**Question:** Как project-specific code подключается в v0.1?
**Status:** answered
**Answer:** Importable local `docengine_project` package configured in `docengine.toml`; Python entry-point plugins may be added later.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q2.2 — owner: `implementer` [BLOCKING]
**Question:** Как регистрировать builders: decorators, explicit registry или оба?
**Status:** answered
**Answer:** Explicit registry as canonical mechanism with decorator convenience that writes into it.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q2.3 — owner: `implementer` [BLOCKING]
**Question:** Разрешать ли builder читать filesystem/JSON напрямую в обход context?
**Status:** answered
**Answer:** No for tracked inputs: project builder may call pure helpers, but dependency-bearing reads must go through context/resolver; escape hatch must be explicit and unaudited.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q2.4 — owner: `implementer` [BLOCKING]
**Question:** Что делать с dependency cycles?
**Status:** answered
**Answer:** Treat as configuration/build error in v0.1; report exact cycle path.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q2.E1 — owner: `implementer` [BLOCKING]
**Question:** P2 introduces executable project code; where may the configured project package live?
**Status:** answered
**Answer:** Project package is confined to project root, must live outside docs, and all package-tree symlinks are rejected before import.
**Decision:** Project package is confined to project root, must live outside docs, and all package-tree symlinks are rejected before import.

### Q2.E2 — owner: `implementer` [BLOCKING]
**Question:** What exact runtime value is persisted/returned by a builder before P3 exists?
**Status:** answered
**Answer:** Implemented immutable DerivedObject + direct tracked-read provenance and version/digests; persistent receipts remain P3.
**Decision:** Implemented immutable DerivedObject + direct tracked-read provenance and version/digests; persistent receipts remain P3.

### Q2.E3 — owner: `implementer` [BLOCKING]
**Question:** Should arbitrary Python builder outputs be accepted and coerced?
**Status:** answered
**Answer:** Non-JSON values, non-string keys and NaN/Infinity are rejected; mutable returned containers cannot mutate the derived result afterward.
**Decision:** Non-JSON values, non-string keys and NaN/Infinity are rejected; mutable returned containers cannot mutate the derived result afterward.

### Q2.E4 — owner: `implementer` [BLOCKING]
**Question:** Does implementing project-package loading and a new derived envelope add acceptance risks not present in the original P2 axis list?
**Status:** answered
**Answer:** P2 acceptance axes expanded to include documentation/code ownership, new contract/version/path risks and release/handoff integrity.
**Decision:** P2 acceptance axes expanded to include documentation/code ownership, new contract/version/path risks and release/handoff integrity.

### Q2.E5 — owner: `implementer` [BLOCKING]
**Question:** Should `docengine rebuild` be wired in P2 merely because BuildEngine now exists?
**Status:** answered
**Answer:** `rebuild` remains an honest stub; docs explicitly distinguish the implemented P2 API from later CLI orchestration.
**Decision:** `rebuild` remains an honest stub; docs explicitly distinguish the implemented P2 API from later CLI orchestration.

### Q2.E6 — owner: `implementer` [BLOCKING]
**Question:** Must every builder target have a documentation-owned derived descriptor?
**Status:** answered
**Answer:** Implemented asymmetric rule: internal targets may be code-only; existing derived descriptors are never treated as raw fallback and must resolve to builders.
**Decision:** Allow internal code-only derived targets; require builder for every derived_descriptor and derived_descriptor kind for any builder target that also exists as a managed resource.

### Q2.E7 — owner: `implementer` [BLOCKING]
**Question:** May file:// tracked reads address _structured, _dependency, or generated managed views?
**Status:** answered
**Answer:** ResourceCatalog now rejects file:// reads/versions unless the path is inventoried as plain canonical Markdown.
**Decision:** Restrict file:// to plain canonical Markdown in v0.1.

### Q2.E8 — owner: `implementer` [BLOCKING]
**Question:** Can callers bypass ref validation by constructing ResourceRef directly instead of parsing a string?
**Status:** answered
**Answer:** ResourceRef now validates direct construction and ResourceRef.parse requires exact canonical round-trip.
**Decision:** Canonical identity is enforced for both object construction and string parsing.

### Q2.E9 — owner: `implementer` [BLOCKING]
**Question:** If project_package is documented as dotted, must nested packages retain normal parent-relative import semantics?
**Status:** answered
**Answer:** Loader now executes package segments under a private prefix and supports parent-relative imports without adding project root as a public global package.
**Decision:** Support dotted packages as documented rather than narrowing the config contract.

### Q2.E10 — owner: `implementer` [BLOCKING]
**Question:** How is builder-code change represented in provenance before P3 invalidation exists?
**Status:** answered
**Answer:** Project extensions now compute a sha256 source revision over project-owned Python source and every derived provenance records builder_revision.
**Decision:** Builder source revision is part of deterministic provenance and will become a P3 invalidation input.

### Q2.E11 — owner: `implementer` [BLOCKING]
**Question:** Is comparator selection builder-wide or dependency-specific?
**Status:** answered
**Answer:** DependencyRead now records its own comparator; BuildContext read/get accept per-read override with builder comparator as default.
**Decision:** Comparator semantics are per dependency, with a builder-level default only.

### Q2.E12 — owner: `implementer` [non-blocking]
**Question:** Can audit_complete be interpreted as proof that arbitrary Python performed no hidden I/O?
**Status:** answered
**Answer:** BuildProvenance now exposes tracking_assurance=cooperative and docs explicitly prohibit treating audit_complete as sandbox proof.
**Decision:** v0.1 uses cooperative trusted project code; stronger isolation may be evaluated later without overstating current assurance.

### Q2.E13 — owner: `implementer` [BLOCKING]
**Question:** Can ResourceCatalog expose a derived_descriptor as raw domain data before/without BuildEngine resolution?
**Status:** answered
**Answer:** ResourceCatalog now rejects raw get/version for derived_descriptor; BuildEngine resolves registered derived targets before consulting the raw store.
**Decision:** Descriptor data is metadata-only and never raw fallback truth.

### Q2.E14 — owner: `implementer` [BLOCKING]
**Question:** If a parent __init__.py imports the configured dotted child package, may the loader execute that child again?
**Status:** answered
**Answer:** The loader reuses an already-loaded child under the private synthetic root and verifies that its __file__ matches the expected package __init__.py.
**Decision:** Dotted project packages preserve single-execution relative-import semantics.

### Q2.E15 — owner: `implementer` [BLOCKING]
**Question:** Should a whole structured-resource dependency version change when only JSON formatting or $docengine materialization metadata changes?
**Status:** answered
**Answer:** ResourceCatalog.version(resource://whole) now hashes canonical domain data, while source_hash remains the physical file hash.
**Decision:** Whole structured-resource dependency identity is domain-data based in v0.1.

## P3 — Dependency receipts, baselines, comparators, diff and state

### Q3.1 — owner: `implementer` [BLOCKING]
**Question:** Как хранить baseline snapshots: per-target files или content-addressed blobs?
**Status:** answered
**Answer:** Content-addressed normalized blobs referenced by receipts; target history lives in receipts/events.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q3.2 — owner: `implementer` [BLOCKING]
**Question:** Какие comparators обязательны в v0.1?
**Status:** answered
**Answer:** `exact`, `json_structured`, `sequence`, `set`, `text_unified`; Markdown AST/semantic comparator deferred.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q3.3 — owner: `user` [BLOCKING]
**Question:** Должен ли `check` изменять dependency state?
**Status:** answered
**Answer:** Проверка зависимостей должна при обнаружении изменения сразу отражать stale/review состояние; semantic validity затем проверяет пользователь/AI.
**Decision:** `check` обновляет runtime dependency state/events, но не canonical content и не validated baseline.

### Q3.4 — owner: `implementer` [BLOCKING]
**Question:** Какие status значения считаем каноническими?
**Status:** answered
**Answer:** At least `valid`, `stale`, `build_required`, `review_required`, `invalid`; `stale` may be umbrella in human text but machine state uses the more specific state when known.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q3.5 — owner: `implementer` [BLOCKING]
**Question:** Нормализуем ли Markdown перед baseline/hash в v0.1?
**Status:** answered
**Answer:** Use raw UTF-8 normalized line endings for v0.1 text comparator; add AST-aware comparator later.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q3.6 — owner: `implementer` [BLOCKING]
**Question:** Как P3 должен учитывать изменение builder/helper code при неизменных data dependencies?
**Status:** answered
**Answer:** Persist the P2 builder_revision/source revision in builder receipts/state and compare it during check; revision change produces build_required for deterministic targets.
**Decision:** Treat builder source revision as a first-class invalidation input in P3.

### Q3.7 — owner: `implementer` [BLOCKING]
**Question:** What exactly does a whole structured resource dependency snapshot/compare in P3: domain data only or the entire managed JSON envelope?
**Status:** answered
**Answer:** Use the entire domain data object/array as the v0.1 whole structured-resource baseline; do not let unrelated $docengine materialization metadata drive derivation invalidation.
**Decision:** P3 baselines/diffs for whole structured resources operate on domain data, while observed source/version metadata may remain diagnostic evidence.

### Q3.8 — owner: `implementer` [non-blocking]
**Question:** How precise must builder code revision invalidation be in v0.1?
**Status:** answered
**Answer:** Use the package-wide content revision in v0.1. Accept possible extra build_required targets rather than risk missing helper-code changes.
**Decision:** Correctness-first conservative code invalidation for v0.1; revisit granularity only with evidence of excessive rebuild noise.

### Q3.E1 — owner: `implementer` [non-blocking]
**Question:** Should read-only dependency query commands create `_dependency` directories when none exist?
**Status:** answered
**Answer:** No. Read-only commands must inspect without creating runtime directories.
**Decision:** `status`, `diff`, `explain`, `history`, and `graph` remain read-only. Stores create parent directories only on actual writes.

### Q3.E2 — owner: `implementer` [BLOCKING]
**Question:** How should P3 classify a target when a required source or current builder cannot be loaded?
**Status:** answered
**Answer:** Use `invalid`, preserving the diagnostic reason (`source_unavailable` or `builder_unavailable`).
**Decision:** Unavailable evidence is not a semantic diff. P3 records `invalid` until the source/builder can be inspected again.

### Q3.E3 — owner: `implementer` [BLOCKING]
**Question:** Can a P2 build with `audit_complete=false` be persisted as `valid` in P3?
**Status:** answered
**Answer:** No. Preserve the receipt for diagnostics but state must be `invalid` with `audit_incomplete`.
**Decision:** P3 never labels an incompletely tracked build as valid.

### Q3.E4 — owner: `implementer` [non-blocking]
**Question:** Should P3 invent a virtual ref syntax for `field_set` or `collection` granularities?
**Status:** answered
**Answer:** No. Aggregate builders persist the many exact canonical refs they consumed; virtual collection addressing is deferred until there is a real addressing contract.
**Decision:** Executable v0.1 receipt granularity is limited to `field`, `resource`, and `whole_file`; conceptual aggregate semantics remain supported through multiple edges.

### Q3.E5 — owner: `implementer` [non-blocking]
**Question:** Should persisted status/history/graph diagnostics require the current project builder package to import successfully?
**Status:** answered
**Answer:** No. Persisted status/history/graph read only dependency state. `check/diff/explain` attempt current builders but degrade to explicit unavailable diagnostics instead of erasing state.
**Decision:** Diagnostic read-side remains available independently of current executable project code.

### Q3.E6 — owner: `implementer` [non-blocking]
**Question:** How should receipt tampering be detected without sacrificing idempotent receipt identity?
**Status:** answered
**Answer:** Keep deterministic `receipt_id` over logical stable content and add `receipt_hash` over the full persisted receipt including `validated_at`.
**Decision:** Retries remain idempotent while edits to persisted receipt metadata/content are detectable.

### Q3.E7 — owner: `implementer` [BLOCKING]
**Question:** Should an explicit semantic/validation receipt also pin the revision of the target that was reviewed?
**Status:** answered
**Answer:** Yes. Explicit receipts automatically record the current target revision and compare it during check/diff.
**Decision:** `record_explicit` pins `target_revision`; target edits produce `target_changed_since_validation`, while an unavailable target produces `target_unavailable` and `invalid`.

### Q3.E8 — owner: `implementer` [BLOCKING]
**Question:** How strict must cross-link integrity be between state/events and their referenced receipt?
**Status:** answered
**Answer:** Cross-links are validated against the referenced receipt, including changed-dependency membership and active-receipt state identity.
**Decision:** `verify_integrity` rejects unknown changed dependencies, target mismatches, missing receipts and `valid` state over incomplete audit receipts. It does not infer current selection from receipt timestamps.

### Q3.E9 — owner: `implementer` [BLOCKING]
**Question:** Should persisted receipt/event parsing trust JSON coercions or enforce the schema-critical primitive types at runtime?
**Status:** answered
**Answer:** Strict runtime parsing is required for receipt/event audit-critical fields.
**Decision:** Receipt/event loaders reject wrong primitive types, invalid source kinds and non-canonical event targets instead of coercing them.

### Q3.E10 — owner: `implementer` [BLOCKING]
**Question:** How should content-stable receipt identity coexist with repeated activation history when a target moves A → B → A?
**Status:** answered
**Answer:** Use content-stable receipts for evidence identity and monotonic state_revision for transition-occurrence identity.
**Decision:** State, graph and integrity use the active receipt selected by persisted state. Every changed state increments state_revision; event IDs include that revision, so exact retries remain idempotent while A→B→A records all three occurrences.

## P4 — Semantic dependencies and review workflow

### Q4.1 — owner: `implementer` [BLOCKING]
**Question:** Делаем ли `--reason` обязательным для semantic validation?
**Status:** answered
**Answer:** Yes. Non-empty `--reason` is required for explicit semantic `still-valid` and `updated` decisions.
**Decision:** Require a review reason so semantic acceptance remains portable and auditable.

### Q4.2 — owner: `implementer` [BLOCKING]
**Question:** Нужен ли ручной `force-valid` обход review в v0.1?
**Status:** answered
**Answer:** No normal force-valid path in v0.1; recovery/admin repair must be a separate explicit future capability.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q4.3 — owner: `user` [non-blocking]
**Question:** Поддерживаем ли dependency target на конкретную Markdown section в v0.1?
**Status:** answered
**Answer:** No. v0.1 does not support dependencies targeting a Markdown section. If a dependency must target only part of a document, that part must be represented as structured JSON and addressed there.
**Decision:** Do not implement Markdown section-level dependency addressing in v0.1. Use whole-file Markdown dependencies; for partial-document dependency granularity, promote the relevant content to structured JSON.

### Q4.4 — owner: `implementer` [BLOCKING]
**Question:** Нужно ли хранить actor metadata для review?
**Status:** answered
**Answer:** Store `actor_kind` = human|ai|ci|unknown and optional free-form non-sensitive actor label; no identity required.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q4.E1 — owner: `implementer` [BLOCKING]
**Question:** Must `validate` carry an explicit review-context token from the reviewed packet?
**Status:** answered
**Answer:** Require deterministic `review_context_id` from `explain`; reject validation when current context no longer matches.
**Decision:** P4 `validate` requires `--review-context`; the token fingerprints target revision, rule revision, active prior receipt and exact current dependency versions.

### Q4.E2 — owner: `implementer` [BLOCKING]
**Question:** Should semantic-rule import fail when a currently declared target/source file is missing?
**Status:** answered
**Answer:** Validate rule syntax/comparators/cycles at registration, but treat current target/source availability as runtime review/check evidence.
**Decision:** Semantic rule registration no longer resolves current content during extension import; missing runtime inputs surface through review/check instead.

### Q4.E3 — owner: `implementer` [non-blocking]
**Question:** How should a newly registered semantic rule with no validated receipt appear in `check` without fabricating evidence?
**Status:** answered
**Answer:** Report an ephemeral `review_required`/initial-validation item with review context; persist nothing until explicit validate succeeds.
**Decision:** P4 `check_all` surfaces registered-unvalidated rules without writing dependency state or fake receipts.

### Q4.E4 — owner: `implementer` [non-blocking]
**Question:** What does `updated` mean during initial validation or when target content did not change?
**Status:** answered
**Answer:** Initial validation uses `still-valid`; `updated` requires a prior validated target and a changed current target revision.
**Decision:** `updated` is rejected for initial validation and for unchanged target content; `still-valid` rejects edited target content.

### Q4.E5 — owner: `implementer` [non-blocking]
**Question:** Can one exact target simultaneously own a deterministic builder receipt and a semantic-review receipt in v0.1?
**Status:** answered
**Answer:** Reject exact whole-target overlap in v0.1; a field-level semantic ref remains a distinct target ref. Revisit only with explicit multi-receipt state semantics.
**Decision:** Project extension validation rejects exact builder/semantic target overlap.

### Q4.E6 — owner: `implementer` [non-blocking]
**Question:** How should review history explain a rule change that removes a previously validated dependency?
**Status:** answered
**Answer:** For semantic validation events, validate reviewed changed dependencies against the union of current receipt sources and the referenced prior receipt sources.
**Decision:** Integrity follows `review.prior_receipt_id` and permits removed prior dependencies while still rejecting unexplained sources.

### Q4.E7 — owner: `implementer` [non-blocking]
**Question:** Do P4 persisted schema additions require a state-schema version bump?
**Status:** answered
**Answer:** Keep persisted schema version 1.0.0 because additions are optional/backward-compatible; strict readers accept legacy P3 evidence and validate new fields when present.
**Decision:** P4 adds optional receipt/event fields without changing required legacy fields; full P0–P3 regression remains part of acceptance.

### Q4.E8 — owner: `implementer` [BLOCKING]
**Question:** How should semantic review-context identity behave when content-stable receipt/dependency state recurs in A → B → A → B cycles?
**Status:** answered
**Answer:** Review context now includes the latest target occurrence revision; consumed-context retry is accepted only when its semantic event remains the active target event/state.
**Decision:** Semantic retries are occurrence-aware: exact retry stays idempotent, while recurrent A/B states create new review contexts and new state-transition events.

### Q4.E9 — owner: `implementer` [BLOCKING]
**Question:** Which status should `check` use when a semantic rule is initially unvalidated, lacks legacy rule metadata, or changes dependency type?
**Status:** answered
**Answer:** Semantic check classification now uses the current rule type consistently for initial, legacy-metadata and rule-type-change paths.
**Decision:** Semantic targets are checked once with the current rule type; rule-type changes do not first persist an event classified by the previous receipt type.

### Q4.E10 — owner: `implementer` [BLOCKING]
**Question:** Where must semantic CLI input validation occur so `--json` remains a reliable machine protocol?
**Status:** answered
**Answer:** actor_kind validation now happens in SemanticReviewRuntime; dependency/semantic CLI boundaries catch RefError.
**Decision:** Invalid actor kinds and malformed target refs return exit 2 with the normal versioned JSON error envelope.

## P5 — Renderers, materialization, drift detection and sync

### Q5.1 — owner: `implementer` [BLOCKING]
**Question:** Как определять ownership/drift generated Markdown: marker в файле или digest в runtime state?
**Status:** answered
**Answer:** Use explicit materialization registration + stored output digest/provenance; do not require visible marker in document content by default.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q5.2 — owner: `implementer` [BLOCKING]
**Question:** Какой режим `sync` default: affected-only или full materialize?
**Status:** answered
**Answer:** Affected-only by default; `--all`/clean mode for explicit full regeneration.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q5.3 — owner: `implementer` [BLOCKING]
**Question:** Что возвращает `sync`, если deterministic work успешен, но остались semantic `review_required`?
**Status:** answered
**Answer:** Command completes successfully as an operation but machine result reports `attention_required`; reserve a documented distinct exit code for unresolved review when desired by automation.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q5.4 — owner: `user` [BLOCKING]
**Question:** Нужен ли filesystem watch/daemon в первой рабочей версии?
**Status:** answered
**Answer:** Основная модель — обычная запускаемая программа с командами; background watch не должен быть обязательным механизмом.
**Decision:** Explicit CLI/sync canonical; watch optional/deferred.

### Q5.E1 — owner: `implementer` [non-blocking]
**Question:** How should P5 sync treat a mixed dependency cycle where a semantic target depends on a derived builder target that in turn reads the semantic target?
**Status:** answered
**Answer:** Permit mixed semantic↔deterministic SCCs only with bounded sync: deterministic members run at most once per sync occurrence; semantic members are never auto-accepted and affected mixed SCCs return attention_required. Pure deterministic executable cycles remain errors.
**Decision:** Permit mixed semantic↔deterministic SCCs only with bounded sync: deterministic members run at most once per sync occurrence; semantic members are never auto-accepted and affected mixed SCCs return attention_required. Pure deterministic executable cycles remain errors.

### Q5.E2 — owner: `implementer` [non-blocking]
**Question:** What should sync do when a previously registered materialization target is removed or renamed and its old generated file now looks like ordinary Markdown?
**Status:** answered
**Answer:** Preserve and report orphaned materialization state; do not perform destructive cleanup automatically. Provide an explicit acknowledgement path that preserves both the file and prior ownership/provenance while marking the orphan resolved for future sync.
**Decision:** Removed/renamed materialization targets are non-destructive attention items. Full regeneration writes only currently registered targets and never deletes former targets. Intentional ownership transitions are resolved with explicit orphan acknowledgement (`materialize file://PATH --ack-orphan`), which preserves file bytes and historical provenance and sets `orphan_acknowledged=true`.

### Q5.E3 — owner: `implementer` [non-blocking]
**Question:** How should a user/agent resolve an intentionally orphaned materialization record after ownership is removed, without deleting a file that may now be canonical Markdown?
**Status:** answered
**Answer:** Use `materialize file://PATH --ack-orphan`. The file is preserved, prior owner/renderer/input/output provenance remains in materialization state, and `orphan_acknowledged=true` makes later sync treat the orphan as acknowledged.
**Decision:** Orphan repair is explicit, non-destructive and provenance-preserving; no automatic deletion or silent state pruning.

### Q5.E4 — owner: `implementer` [non-blocking]
**Question:** Should P3/P4 dependency and semantic diagnostics require successful registration of P5 project renderers?
**Status:** answered
**Answer:** No. Renderer registration is component-scoped and is loaded only when a P5 command needs it; dependency/semantic diagnostics remain available independently.
**Decision:** Project extension loading separates renderer registration from dependency/semantic diagnostic paths. Renderer failures remain JSON-envelope errors for P5 commands only.

## P6 — Complete CLI and AI/CI operating protocol

### Q6.1 — owner: `implementer` [BLOCKING]
**Question:** Как выглядит canonical JSON envelope для всех CLI команд?
**Status:** answered
**Answer:** Top-level: `schema_version`, `command`, `ok`, `attention_required`, `data`, `warnings`, `errors`, `meta`.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q6.2 — owner: `implementer` [BLOCKING]
**Question:** Фиксируем ли единый набор exit codes?
**Status:** answered
**Answer:** Yes. Recommended: 0 success/no blocking attention; 2 completed but attention/review required; 3 verification/domain validation failure; 4 usage/config error; 5 internal/runtime failure.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q6.3 — owner: `implementer` [BLOCKING]
**Question:** Какие команды строго read-only?
**Status:** answered
**Answer:** `status`, `diff`, `explain`, `history`, `graph`, `resources`, and `verify` are read-only; `check`, `sync`, `rebuild`, `validate`, `materialize`, and `init` may mutate only the state/output documented for each command.
**Decision:** Freeze query/mutation boundaries in CLI contract and test them.

### Q6.4 — owner: `implementer` [BLOCKING]
**Question:** Нужно ли поддерживать stdin/stdout-only режим для агента?
**Status:** answered
**Answer:** JSON stdout is mandatory; structured stdin for bulk actions deferred unless a concrete use case appears.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q6.E1 — owner: `implementer` [BLOCKING]
**Question:** Does freezing the Q6.1 envelope require a machine-output schema-version bump?
**Status:** answered
**Answer:** Yes. Freeze the P6 canonical envelope as machine schema 2.0.0.
**Decision:** Machine output schema is bumped from 1.0.0 to 2.0.0; the new top level is exactly `schema_version`, `command`, `ok`, `attention_required`, `data`, `warnings`, `errors`, `meta`.

### Q6.E2 — owner: `implementer` [BLOCKING]
**Question:** Can a read-only CLI command import project code if that import writes Python bytecode into the project?
**Status:** answered
**Answer:** No. Project extension loading must suppress bytecode writes while preserving the caller process setting afterwards.
**Decision:** Project package import and lazy registration imports run with temporary `sys.dont_write_bytecode=True`; the previous global value is restored in `finally`.

### Q6.E3 — owner: `implementer` [non-blocking]
**Question:** Which deterministic builders are independently required by `verify`?
**Status:** answered
**Answer:** Release-gate documentation-owned derived descriptors and active recorded targets; do not require standalone receipts for internal-only helper builders.
**Decision:** `verify` executes/checks managed `derived_descriptor` targets and persisted active receipts; internal-only helpers are verified transitively when required builders execute.

### Q6.E4 — owner: `implementer` [BLOCKING]
**Question:** Should `verify` fail fast when one project extension component is broken?
**Status:** answered
**Answer:** No. Load base builder/semantic components and renderer component separately; record component failures as findings and continue independent integrity/state checks.
**Decision:** Verification aggregates component findings and continues dependency/state checks; renderer failure cannot erase persisted dependency diagnostics.

### Q6.E5 — owner: `implementer` [BLOCKING]
**Question:** Is the configured project Python package mandatory for `verify` on a documentation-only project?
**Status:** answered
**Answer:** No. Documentation-only projects verify without creating a placeholder project package.
**Decision:** `verify` only loads the project package when it exists. Missing required builders are still reported for documentation-owned derived descriptors.

### Q6.E6 — owner: `implementer` [BLOCKING]
**Question:** How should `verify` behave if the dependency runtime cannot even be constructed because its machine-owned root is unsafe/corrupt?
**Status:** answered
**Answer:** Verification now reports `dependency_runtime_unavailable` inside the complete report and continues independent builder/component checks where possible.
**Decision:** Domain corruption of dependency runtime is exit 3 verification evidence, not exit 5 internal failure.

### Q6.E7 — owner: `implementer` [BLOCKING]
**Question:** May explicit project/documentation roots be nonexistent paths or regular files and still verify as an empty clean project?
**Status:** answered
**Answer:** Root discovery now rejects nonexistent/non-directory project roots and existing non-directory documentation roots.
**Decision:** Invalid root shape is usage/config error (exit 4), never a clean verification success.

### Q6.E8 — owner: `implementer` [BLOCKING]
**Question:** Should accidental `SystemExit` from project imports/registration/builders/renderers be allowed to escape the machine protocol?
**Status:** answered
**Answer:** Project import/registration/builder/renderer `SystemExit` is wrapped into engine domain/component errors and remains inside the JSON protocol.
**Decision:** Catch `SystemExit` specifically at project callback boundaries; cooperative code is still not sandboxed.

### Q6.E9 — owner: `implementer` [non-blocking]
**Question:** When a human CLI command fails or requires attention but already has structured diagnostic data, may the human renderer collapse it to only a status/roots line?
**Status:** answered
**Answer:** Human dependency/orchestration output now preserves available diagnostic data on non-success; verify usage/config errors fall back to the generic issue renderer when no report exists.
**Decision:** Human output may summarize but must not discard the core diagnostic facts already present in `CommandResult.data`.

### Q6.E10 — owner: `implementer` [non-blocking]
**Question:** How is the claimed CLI registry/parser parity protected against future drift?
**Status:** answered
**Answer:** A dedicated P6 regression test now compares `CLI_COMMANDS.json` with the actual argparse surface and exit-code table.
**Decision:** Registry/parser parity is executable assurance rather than documentation-only intent.

### Q6.E11 — owner: `implementer` [BLOCKING]
**Question:** Should P6 verification reclassify a receipt with an unavailable semantic rule using only the old receipt dependency type?
**Status:** answered
**Answer:** Verification current-check classification now mirrors the canonical runtime semantics, including `semantic_rule_unavailable → invalid` and `audit_complete=false → invalid`.
**Decision:** Verify does not maintain a weaker parallel status classifier.

## P7 — Hardening, recovery, migrations and scalability

### Q7.1 — owner: `implementer` [BLOCKING]
**Question:** Какую concurrency model фиксируем для первого hardened release?
**Status:** answered
**Answer:** Single writer per documentation root via lock; concurrent read-only commands allowed when safe.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q7.2 — owner: `implementer` [BLOCKING]
**Question:** Когда обязательна migration, а когда допустим reset runtime state?
**Status:** answered
**Answer:** Canonical/document data never reset. Persisted dependency state formats require migrations once released; reset allowed only for explicitly disposable caches, not receipts/history/baselines.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q7.3 — owner: `implementer` [non-blocking]
**Question:** Какой synthetic scale и performance budget принять?
**Status:** answered
**Answer:** Start benchmark fixture at 10k resources / 50k dependency edges; establish measured baseline in P8, then record an environment-normalized budget before acceptance.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q7.4 — owner: `implementer` [non-blocking]
**Question:** Нужен ли watch mode вообще в v0.x?
**Status:** answered
**Answer:** Keep optional and out of acceptance unless explicit-command workflow proves insufficient.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q7.E1 — owner: `implementer` [non-blocking]
**Question:** Should recognized P6 runtime evidence require a separate manual migration before every P7 mutation?
**Status:** answered
**Answer:** No. Keep explicit `migrate`, but allow recognized P6 layout to migrate automatically inside the same exclusive transaction before a normal mutation.
**Decision:** Recognized legacy P6 layout auto-migrates transactionally; unknown/future versions still fail and are never reset.

### Q7.E2 — owner: `implementer` [BLOCKING]
**Question:** Where should the per-documentation-root lock live if read-only commands must not mutate the project?
**Status:** answered
**Answer:** Use an OS-temporary lock path keyed by the resolved documentation root.
**Decision:** P7 uses an external OS lock; project-owned transaction/recovery evidence is created only by mutations.

### Q7.E3 — owner: `implementer` [non-blocking]
**Question:** What should automatic recovery do if a transaction target changed outside the interrupted transaction after the crash?
**Status:** answered
**Answer:** Refuse automatic overwrite. Allow explicit `recover --force` to choose pre-crash rollback, and audit the forced conflict paths.
**Decision:** Default recovery preserves unknown bytes and remains pending; `--force` is an explicit destructive operator decision recorded in recovery history.

### Q7.E4 — owner: `implementer` [non-blocking]
**Question:** How can a transaction preserve read-your-writes while still recovering from a process crash?
**Status:** answered
**Answer:** Use an exclusive lock plus durable pre-images/planned hashes before each immediate atomic file write. Readers cannot enter during the writer; recovery rolls back open journals.
**Decision:** P7 uses write-ahead pre-images with immediate atomic writes under the exclusive lock; journal commit defines command durability.

### Q7.E5 — owner: `implementer` [non-blocking]
**Question:** Should a P6 runtime containing only materialization provenance be treated as empty when no dependency receipts/state exist?
**Status:** answered
**Answer:** No. `materialization_state.json` alone makes the unmarked runtime a legacy P6 layout that requires the registered migration.
**Decision:** Migration detection includes materialization state and the migration preservation digest covers it.

### Q7.E6 — owner: `implementer` [non-blocking]
**Question:** Does a leftover journal with durable `phase=committed` represent a recovery blocker?
**Status:** answered
**Answer:** No. Committed residue is a non-blocking cleanup warning; readers may proceed and `recover`/the next writer removes it.
**Decision:** Read guard blocks only uncommitted journals; verify reports `transaction_cleanup_required` warning for committed residue.

### Q7.E7 — owner: `implementer` [non-blocking]
**Question:** How strict must the runtime-layout marker parser be relative to its JSON Schema?
**Status:** answered
**Answer:** Enforce schema-critical keys/types/provenance/digests/timestamps and reject unknown keys/future versions.
**Decision:** Runtime layout loading now validates the same audit-critical constraints as the schema before treating the layout as current.

### Q7.E8 — owner: `implementer` [BLOCKING]
**Question:** How can P7 complete when P7-A5 says the phase remains partial without a performance budget, Q7.3 defers that budget to P8, P8 says it starts only after P7 acceptance, and the phase schema has no partial status?
**Status:** answered
**Answer:** Accept P7 hardening with DAX18 explicitly partial and promote DAX18 into P8 as a blocking release-gate item.
**Decision:** P7 may be phase-accepted with P7-A5/DAX18 partial because Q7.3 intentionally defers the threshold. P8 acceptance axes now include DAX18 and P8-A8 requires a recorded normalized budget and passing benchmark before final release acceptance.

### Q7.E9 — owner: `implementer` [BLOCKING]
**Question:** May recovery execute a transaction journal that is syntactically/schema-valid but semantically inconsistent with its directory, pre-images, or current filesystem state?
**Status:** answered
**Answer:** No. Corrupt or semantically impossible journals are never executable recovery instructions.
**Decision:** Recovery fully validates the journal and all operations before changing files; transaction-id/path mismatches, impossible existed/backup/hash relationships and rogue transaction entries remain `recovery_required` without mutation.

### Q7.E10 — owner: `implementer` [BLOCKING]
**Question:** Can a runtime-layout marker self-assert migration provenance, or must migrated_from/migration_id correspond to the registered migration and validated released evidence?
**Status:** answered
**Answer:** Migration provenance is registry-bound, not self-authenticating.
**Decision:** Runtime-layout loading validates migrated provenance against `MIGRATIONS.json`/runtime registry; migration refuses symlinked or structurally/integrity-corrupt released evidence and never writes a current marker on failure.

### Q7.E11 — owner: `implementer` [non-blocking]
**Question:** Are P7 migration/recovery audit logs themselves verification evidence, or may corrupt logs be ignored once the runtime files look usable?
**Status:** answered
**Answer:** Hardening audit logs are verification evidence and corruption is blocking.
**Decision:** `verify` validates migration/recovery JSONL records and reports corruption through the complete-report envelope; corrupt dependency receipts similarly remain report findings rather than exit-5 internal errors.

## P8 — Final verification, release gate, portability and handoff

### Q8.1 — owner: `user` [BLOCKING]
**Question:** Должен ли release verify разрешать `review_required` по умолчанию?
**Status:** answered
**Answer:** No. `docengine verify` must always emit its complete verification report. If unresolved `review_required` or another blocking issue exists, the report returns `ok=false` and the CLI returns a non-zero exit code; this is a verification result, not an execution crash.
**Decision:** Treat unresolved required review as a blocking verification result by default. `verify` is read-only, always reports findings, uses `ok=false` for failed verification, and returns a non-zero exit code for machine/CI signaling.

### Q8.2 — owner: `implementer` [BLOCKING]
**Question:** Какой артефакт передачи считаем основным: wheel, source archive или оба?
**Status:** answered
**Answer:** Both: source archive containing docs/examples/tests + buildable wheel; source archive is canonical handoff artifact.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q8.3 — owner: `implementer` [BLOCKING]
**Question:** Что входит в engine release manifest, а что считается volatile project runtime state?
**Status:** answered
**Answer:** Engine manifest tracks package/spec/examples/tests. Project runtime state is verified by project-level commands and not embedded as engine release integrity state.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q8.4 — owner: `implementer` [BLOCKING]
**Question:** Нужна ли compatibility guarantee до 1.0?
**Status:** answered
**Answer:** Persisted formats are explicitly versioned from v0.1; breaking changes allowed pre-1.0 only with migration or clear reset path documented and tested.
**Decision:** Adopt this implementation default for v0.1 unless implementation evidence exposes a contradiction.

### Q8.E1 — owner: `implementer` [BLOCKING]
**Question:** How should the P7 10k/50k benchmark be normalized so P8 does not bind release acceptance to one host clock speed?
**Status:** answered
**Answer:** Use pure_python_integer_mix_v1 calibration (3,000,000 iterations, five samples, median) and require normalized total ratio <= 4.0, RSS <= 256 MiB, and exact 10k/50k + 10k diff/render counts.
**Decision:** The budget is stored in spec/release/PERFORMANCE_BUDGET.json before the release rerun; performance evidence records its SHA-256 and P8 acceptance is blocked unless every check passes.

### Q8.E2 — owner: `implementer` [non-blocking]
**Question:** Should bundled sample_project ship already semantically validated, or preserve its initial-review onboarding state?
**Status:** answered
**Answer:** Preserve the initial-review sample state and verify the complete sync→explain→validate→sync→verify lifecycle in release_check.py.
**Decision:** The release archive does not bake human/AI semantic acceptance into the onboarding sample merely to make its initial verify pass. P8-A2 is demonstrated on a clean temporary copy.

### Q8.E3 — owner: `implementer` [non-blocking]
**Question:** How should P8 close the Windows shared-reader locking portability watch item for v0.1?
**Status:** answered
**Answer:** Safe Windows `msvcrt` serialization is accepted for v0.1. POSIX supports concurrent shared readers; Windows concurrent-reader parity is not guaranteed or release-gating.
**Decision:** Close A7 as an accepted v0.1 support limitation, not an unresolved watch item.

### Q8.E4 — owner: `implementer` [BLOCKING]
**Question:** How should the phase model represent a phase-local partial criterion intentionally carried into a later release gate?
**Status:** answered
**Answer:** Use canonical `carried_release_gates`. P7-CG1 carries P7-A5/DAX18 to P8-A8 and is marked resolved only because P8-A8 and P8/DAX18 pass.
**Decision:** Accepted phases may contain `partial` only when the exact source criterion/axis is covered by an explicit carry. Final P8 release rejects open carries.
