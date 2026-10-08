# Field dependency expansion — agreed implementation plan

**Decision:** `FIELD-EXPANSION-1`, 2026-10-07. **Execution status: implemented; local acceptance passed. Remote platform matrix not executed.**

This is the canonical additive follow-up to [`FIELD_DEPENDENCY_AUTHORING.md`](FIELD_DEPENDENCY_AUTHORING.md). The agreed requirements below are implemented in runtime `0.1.0.dev23` and the copyable project helper; fresh local acceptance is recorded in section 10. Historical P0–P8 acceptance and `FIELD-AUTHORING-1` evidence are preserved. This plan does not create a new accepted release phase.

The user requires independent nested fields, agreed to retain current recursive depth behavior, and requested that the remaining decisions and plan gaps be recorded. Core error handling and operation-scoped reuse now belong to the implementation scope. Remote branch/PR/release publication remains deferred under the user's earlier direction.

## 1. Goal and deliverables

Allow project Python to compute a requested field from raw or computed fields at arbitrary object nesting, without completing unrelated siblings or their containing document. Compose finished objects/documents from those fields, preserve tracked dependency evidence, diagnose genuine cycles and unavailable sources, and avoid repeated successful producer execution within one stable operation.

Deliverables:

- A backward-compatible extension of the copyable `FieldPlan`, nested declarations/reads/overrides and composition.
- The shared runtime fix for transitive derived-source failures found as review issue **P-2**.
- An explicit operation-scoped build context shared by check, rebuild and materialization paths that participate in the same command.
- Runnable flat/nested fixtures, failure/recovery and real producer-count regressions.
- Updated new-chat and maintainer documentation, synchronized runtime source/wheel/version and release manifest when core changes are implemented.

## 2. Decisions and ownership

| ID | Decision | Owner / rationale |
|---|---|---|
| FE-D01 | Independent fields may be addressed at any object depth; objects at every level can compose independently owned children. | User requirement; a top-level-only boundary can recreate false cycles inside a nested object. |
| FE-D02 | Continue to use whole internal resources for computational units and complete materialized views. Native registration on JSON Pointer is not required. | Existing selected architecture; uses accepted tracked engine APIs. |
| FE-D03 | Required inputs, computed providers and optional raw overrides remain explicit. Missing raw-only input never guesses a derived producer. | Preserve the P-1 fix and source ownership. |
| FE-D04 | Normalize BuilderError only at the derived-source resolution boundary; retain its message/cause and cycle path. | Fix confirmed P-2; preserve existing domain/config/corruption classifiers. |
| FE-D05 | Reuse successful values/provenance within one command/operation with stable source/code evidence. No process-global or persistent value cache. | Agreed repeat-execution goal; avoid reuse across changed inputs. |
| FE-D06 | Retain recursive execution and the normal Python recursion limit. No automatic limit increase, iterative scheduler or new guaranteed depth number. | User decision. Return only on an actual project exceeding depth; 128-pass/256-fail was environment-specific evidence. |
| FE-D07 | Keep deterministic tracked project producers, immutable successful outputs, explicit semantic verdicts and existing transaction/read-only invariants. | Existing runtime contracts; helper does not sandbox arbitrary Python. |
| FE-D08 | Preserve existing flat-label APIs; introduce explicit pointer-path APIs for nesting. Dots in old labels remain literal. | Implementer default; avoid breaking valid old labels or confusing paths with names. |
| FE-D09 | Array values and source pointers remain supported. Independent fields inside existing arrays use their current index/shape; membership or order changes invalidate their evidence. Array creation/resize/reorder is owned by an atomic array producer or raw input, not implicit sparse path insertion. | Implementer default; support objects inside arrays without inventing ambiguous element identity. |

These decisions are settled for this plan. No user-owned blocking question remains. Technical API signatures/placement can be chosen during implementation within these contracts; record any genuine semantic change before acceptance.

## 3. Nested field and composition contract

### 3.1 Identity and declared sources

Use parsed JSON Pointer tokens for path identity, escaping literal `~` and `/` as `~0` and `~1`. Preserve Unicode, numeric object keys and empty-key pointer tokens. Pointer API names must be explicit; a legacy field label such as `plan.deadline` or `a/~` is still one top-level key.

Declare each document/composition boundary's canonical raw source before registration so a prerequisite can read a nested object before any final-view builder runs. Resolve missing raw-only values as source errors, not filename-based guesses or descriptor reads. A canonical raw document remains separate from a metadata-only derived descriptor and generated Markdown.

Every independent provider has one logical path and a unique whole internal target. Reject duplicate and normalized-equivalent paths/targets before building. A parent producer that returns an object/array owns that whole subtree; independent child providers may not overlap it. Raw data copied by a composite is its base, not a competing computed provider.

Keep existing flat target IDs stable when adopting the extension. New generated aggregate/path IDs must be deterministic and collision-safe. Test adoption on a project with existing receipts and Markdown, not only a fresh fixture. Renaming/removing a registered path/target needs an explicit compatibility/retirement route; never erase historical receipts or edit `_dependency` manually to hide an unavailable old target. If that route is unavailable for a proposed identity change, preserve the old identity or resolve migration before acceptance.

### 3.2 Atomic fields and composite objects

An atomic provider may return any JSON-compatible value, including an object/array. Reading inside such a value completes that provider; the engine cannot split ordinary Python into independent sub-producers. A composite object instead gathers declared independent descendants plus preserved raw fields.

Leaf reads do not complete unrelated siblings. A whole-object read resolves all descendants required for that object. Reading a whole object that includes the currently executing field is a genuine demand cycle; report the path. Never return a mutable, partially completed object as a successful value.

The same composition rules apply to nested objects and the document root. Copy raw structures privately; preserve undeclared raw fields. Create absent intermediate **object** containers when the declared structure requires them. An existing scalar/null where a child object is required is a shape conflict, not permission to silently discard raw data. Numeric tokens are array indices only under an actual declared/existing array; otherwise they are object keys. Reject out-of-range array traversal and implicit sparse/extended arrays.

Computed values must not silently overwrite raw values. Permit precedence only through a matching declared raw override at that canonical location. Presence is distinct from truthiness: null/false/zero/empty values are supplied values. A missing nested key/ancestor in an otherwise valid raw source can select its producer; missing canonical source, wrong container type or invalid array access is an error. Track presence/absence through the addressable raw container; conservative whole-source tracking is acceptable and must be documented.

### 3.3 Required nested fixture

| Requested value | Provider |
|---|---|
| `A#/plan/deadline` | tracked raw calendar field in B |
| `C#/total` | formula reading `A#/plan/deadline` |
| `A#/plan/budget` | formula reading `C#/total` |
| `A#/plan` | complete composition of deadline, budget and preserved raw members |
| final A | complete root composition and ordinary materialization |

Requesting deadline must not invoke C.total or budget. Requesting budget must succeed in order deadline → total → budget. Requesting plan must return the complete object. Existing flat fixtures remain valid.

## 4. Error handling, state and provenance

P-2 is fixed at the derived-source resolver boundary; cold/warm failure and restoration regressions pass. The following failure contract remains part of acceptance. After a successful build, removing transitive C.x or throwing from its producer must make check/sync return the established domain-failure protocol (exit 3), classify affected consumers invalid, and retain useful ref/cause diagnostics. A failed sync must preserve previously materialized Markdown.

Cover first build and previously successful build, direct/transitive prerequisites, a genuine cycle, unknown provider, malformed declaration and restoration after failure. Failed results are never cached as ready or recorded as valid. A new operation can retry restored data/code. Keep direct BuildEngine exception types; normalization belongs at the resolver boundary.

Check/diff/verify must share existing availability/audit semantics; verify remains read-only and aggregates failures. Status/history/graph keep persisted diagnostic semantics and do not become implicit live builders. Preserve the config/corrupt-state distinction rather than converting every exception to an input error.

Every tracked read keeps its version, value slice, provenance and active branch dependencies even when output is unchanged. Switching from a computed source to an equal raw override must update the producer's evidence and drop inactive prerequisites. Reusing a cached DerivedObject must not skip required receipt selection, state/event updates or materialization provenance. Explicit semantic validation is never inferred from a deterministic rebuild.

## 5. Operation-scoped reuse contract

Create one explicit build context per top-level operation; pass it to dependency resolution, deterministic rebuilding, inspection and materialization. For sync this includes initial check → rebuild → final check → inspection/materialization. Merely extending the cache inside one BuildEngine.build call is insufficient. Lower-level library callers need an explicit reuse scope; standalone calls retain safe fresh-scope behavior.

A successful whole-resource producer executes at most once per **stable input/code epoch** within the operation. Repeated exact-slice reads use its immutable value and provenance. Share neither cache nor in-progress stack between projects/registries or separate commands. Cache only successful complete results, and distinguish an in-progress cycle from a cached ready object.

Pin the registry/project-code revision and each whole source's bytes/value/version consistently, including overlapping whole/field/file reads and override presence. Current read-only/transaction locks remain in force. Do not introduce a complete new persistent snapshot format: verify the versions of consumed sources/code before publishing successful evidence/output. If externally changed, fail clearly or restart with a fresh scope; never silently combine cached old values with new observations. Engine-owned writes that affect cached sources require invalidation/a new epoch. No automatic unbounded retries.

Producer-count acceptance applies to successful executions in a stable epoch, not a blanket promise across input mutations, failed attempts or different commands. Persistent cross-command reuse, parallel scheduling and stronger isolation remain outside scope. Package-wide code invalidation and conservative override-container invalidation remain accepted defaults.

## 6. Acceptance matrix

Existing 284-pass/1-skip evidence belongs to the flat implementation. Fresh expansion evidence and the criterion-to-check mapping are in section 10; platform execution is scoped explicitly.

| ID | Scenario / required outcome |
|---|---|
| FE-A01 | Original flat A/B examples and legacy labels remain unchanged; unknown raw-only input never invokes inferred fallback. |
| FE-A02 | Nested deadline → C.total → budget fixture succeeds; a deadline-only request executes no unrelated producer. |
| FE-A03 | Composite reads at intermediate/root levels preserve raw members and return complete values; child reads beneath an atomic provider obey its atomic boundary. |
| FE-A04 | Duplicate/overlapping ownership and target collisions reject during declaration/registration; whole-parent self-demand reports a genuine cycle. |
| FE-A05 | Nested and escaped pointers, dots/slashes/tildes, numeric and empty object keys behave consistently; legacy labels are not reinterpreted. |
| FE-A06 | Missing object ancestors compose when permitted; existing scalar/null ancestors, wrong array types and invalid indices fail without changing raw. |
| FE-A07 | Nested overrides cover add/change/remove and null/false/zero/empty values; unauthorized raw/computed conflicts fail. |
| FE-A08 | Required-source and producer failures work both on cold build and after prior success; transitive check/sync failures are exit 3, invalid state and preserved Markdown. |
| FE-A09 | Restore input/producer after failure: a fresh operation retries successfully, sync/verify pass; failed values and stack state do not leak. |
| FE-A10 | Producer counters prove once per stable operation across shared prerequisites, initial/final checks and materialization, independent of target order. |
| FE-A11 | New command or library scope observes changed data/code; two projects/registries do not share values; consumed-source/code changes within an operation cannot publish stale success. |
| FE-A12 | Equal-value branch/override switches update active receipts/dependencies and remove inactive sources; later inactive-source changes do not rebuild consumers. |
| FE-A13 | Actual branch reads, nested slices, composite membership and array shape changes invalidate correctly; unused independent input remains irrelevant. |
| FE-A14 | Reuse preserves build provenance, receipt activation, state/event idempotence and materialization provenance; retry and existing mixed semantic cycles keep their accepted behavior. |
| FE-A15 | Read-only verify/diff/explain do not persist caches/state or create runtime paths; status/history/graph keep diagnostic-only behavior. |
| FE-A16 | Final nested Markdown output is complete; explicit anchors in multiline text survive built-in rendering; anchor fields do not become computational dependencies. |
| FE-A17 | Independent topological oracle checks flat/nested DAG values with different registration/request orders; raw values remain unchanged. |
| FE-A18 | Existing full suite and spec/axis/manifest/lifecycle checks pass; bundled-wheel installation reproduces the new cold-start fixture. |
| FE-A19 | Onboarding distinguishes installed runtime vs project helper and current vs planned behavior; a new chat can declare, register, sync, graph/explain and verify a nested project. |
| FE-A20 | Depth policy remains recursive with no automatic recursion-limit changes or invented fixed guarantee; focused small-chain regression retains correct behavior. |
| FE-A21 | A populated flat project adopts the extension with stable targets, preserved receipts/history and successful sync/verify; proposed renamed/removed internal targets have an explicit supported compatibility/retirement path. |

## 7. Implementation sequence and release closure

1. Establish explicit pointer/composite ownership APIs and fixtures while preserving flat compatibility. Record technical API choices here.
2. Implement the narrow P-2 resolver fix and failure/recovery regressions before broadening the cache.
3. Extend nested source selection, atomic/composite boundaries and private final composition; test object/array shape and ownership cases.
4. Add a shared operation context, source/code consistency checks and integration across resolver/rebuild/materialization. Use call counters over real commands; checking only return values is insufficient.
5. Exercise the combined nested fixture, adoption of populated flat state, branch/override switching, error/recovery, cycle and read-only/transaction regressions. Compare values independently of the helper.
6. Update FIELD_DEPENDENCIES, BUILD_RUNTIME, CODE_MODEL, AI_USAGE_PROTOCOL, Quickstart/WF06, fixture README and maintainer/system map as required. All claims must describe actual delivered behavior.
7. Because core source changes, assign a new Python runtime build version before rebuilding the single active wheel; synchronize metadata/source/docs and regenerate MANIFEST only with release tooling. Keep historical evidence append-only.
8. Run required ordinary checks and clean bundled-wheel lifecycle. Windows/Python 3.14 and Ubuntu/Python 3.11 remain release matrix requirements; Linux-only evidence is not a Windows readiness claim. Run release-only benchmark if producing a release/tag/handoff, not merely editing this plan.

## 8. Out of scope and return triggers

- **Depth / review D-3:** current recursion retained by user. Return on a real excessive chain; assess tested limit increase first and iterative execution if such chains become routine. Do not confuse recursion exhaustion with a graph cycle.
- **Persistent values / remainder of D-2:** no cross-command cache. Return when measured repeated cost across commands justifies versioned persisted reuse.
- **Native fields / D-1:** no new persisted field-ref/receipt scheme, parallel scheduler or partial-result publication. Return if public pointer-target APIs or atomic groups become a product requirement.
- **Array membership:** shape/order belongs to canonical raw or one array producer. Return if stable dynamic per-element identity or independently inserting/removing elements is needed.
- **Stronger sandbox:** cooperative tracked project Python remains accepted A1. Hidden direct I/O is not made safe by the cache.
- **Methodology migration:** demonstrate compatibility on copied fixtures; bulk editing the supplied methodology repository is a separate task.
- **Remote publication:** no branch/PR/tag/main update is authorized by this plan-recording request.

## 9. Plan completeness check — 2026-10-07

The previous plan lacked explicit contracts for nested ownership/assembly, raw bindings before demand reads, missing intermediate containers, arrays, flat-API and persisted-target compatibility, operation-cache lifetime/source consistency, cache integration across sync phases, failure recovery and core-wheel release closure. Sections 2–7 recorded them before implementation with explicit acceptance criteria.

The existing helpers, resolver, sync, CLI transaction/read-only routes and repository workflow were inspected for this check. This historical paragraph records plan validation before implementation; section 10 records implementation acceptance separately. Remaining choices are implementation details within the agreed contracts; if evidence exposes a semantic choice, record it without reopening settled scope or rewriting historical acceptance.

## 10. Implementation and local acceptance — 2026-10-07

Delivered runtime: **0.1.0.dev23**. Handoff identity: **0.40.0-p8-field-dependency-expansion**. This is an additive implementation record; historical P0–P8 and FIELD-AUTHORING-1 evidence is preserved. No new phase or remote release is claimed.

### 10.1 Delivered API and integration

The copyable helper retains `input`, `computed`, `read`, `compose` and `register`, with old field labels and explicit field target IDs unchanged. It adds `document(document, raw_source)`, `input_path`, `computed_path`, `read_path`, `compose(..., path="/...")`, `describe` and deterministic `object_target(document, path)`. Path APIs parse JSON Pointer tokens. Canonical bindings and inferred composite ancestors are registered before demand evaluation. Atomic providers own their subtrees; composites build private complete object/array values. Matching nested raw overrides and source/container checks enforce the recorded ownership contract.

The installed runtime adds public `BuildOperation(store, registry)`, passed explicitly to `BuildEngine` and `DependencyRuntime`. CLI resolution, check/diff, rebuilding, verification and materialization share one successful-result session per command. Standalone builds retain fresh sessions. Managed JSON is parsed and fingerprinted from the same bytes; consumed sources, materialization descriptors and loaded project Python are checked before evidence/output commit. Observed consistency failures poison the scope even if a producer catches the exception and restores the source. Ordinary failed producers remain retryable; failed results are never ready-cache entries.

P-2 is fixed by normalizing `BuilderError` at derived-source resolution, retaining the original cause/ref/cycle diagnostic. Cold and previously successful transitive failures return domain exit 3; warm checks classify consumers invalid, failed sync preserves generated Markdown, and restored source/code succeeds in a fresh operation. Direct BuildEngine exception classes and existing persisted schemas remain unchanged.

For path/target identity changes, the tested supported route is an explicit compatibility builder retaining the old ID and delegating to the new complete internal value. Automatic target retirement or history deletion is not implemented. The rename regression first proves an unavailable old target fails, then proves the documented alias restores sync/verify without editing runtime state.

### 10.2 Criterion-to-check mapping

All criteria below pass within the local scope. **FE-A18 platform evidence is partial:** Linux/Python 3.12.14, source/package/lifecycle/Git checks pass; Ubuntu/Python 3.11 and Windows/Python 3.14 remote jobs were not run. No Windows readiness claim follows from this record.

Test files: [flat](../tests/test_field_dependency_project.py), [nested](../tests/test_nested_field_project.py), [operation](../tests/test_build_operation.py), [builders](../tests/test_builders.py), [P3](../tests/test_p3_dependencies.py), [P4](../tests/test_p4_semantic.py), [P5](../tests/test_p5_materialization.py), [P6](../tests/test_p6_protocol.py), [onboarding](../tests/test_documentation_workflows.py).

| Criterion | Fresh evidence / regression |
|---|---|
| FE-A01 | Flat fixture lifecycle, demand reads, required-input and unknown-provider tests; legacy dotted labels in nested path regression. |
| FE-A02 | Nested `test_nested_demand_and_complete_parent_composition`; deadline-only counter excludes total/budget, budget yields 50. |
| FE-A03 | Same nested test and atomic subtree test; plan/root preserve raw members, atomic child reads complete their owning provider. |
| FE-A04 | Flat ownership test; nested atomic overlap, registry composite collision, canonical override mismatch and whole-parent self-cycle tests. |
| FE-A05 | Nested paths/shapes/arrays/legacy-names test; escaped slash/tilde, empty keys, numeric object keys and literal dots. |
| FE-A06 | Nested paths/shapes test creates missing object ancestors, rejects scalar/null or invalid array indices, and checks unchanged raw. |
| FE-A07 | Nested falsey overrides and conflict tests plus CLI add/equal/change/remove override workflow. |
| FE-A08 | Flat cold and warm transitive missing-input/producer regressions; existing direct-input lifecycle; exit 3 and preserved Markdown. |
| FE-A09 | Restoration in both transitive regressions; operation failed-producer retry and isolation tests. |
| FE-A10 | Operation `test_actual_cli_commands_execute_each_successful_builder_once` instruments flat/nested sync, check, diff, verify and materialize; shared-scope repeated/order-varied roots also counted. |
| FE-A11 | Operation fresh-scope/isolation, registry changes, actual source/code mutation rollback and caught/restored-source poison tests. |
| FE-A12 | Nested equal-override CLI regression checks changed active receipt, raw-only dependency and unchanged budget receipt/output after inactive C changes; removal restores current formula. |
| FE-A13 | Builders actual-read test, flat unused-input lifecycle, nested array-shape/slice provenance and CLI prerequisite mutations; bound raw tracking remains conservative as documented. |
| FE-A14 | P3 idempotent build/receipt/event and provenance regressions, P4 exact retry, P5 unchanged sync/materialization and mixed semantic SCC regressions; new operation counter tests share those runtime paths. |
| FE-A15 | P3 diagnostic-only test, P6 complete read-only tree test and nested verify/diff/explain/status/history/graph byte-for-byte tree preservation. |
| FE-A16 | Nested source CLI fixture and isolated installed-wheel lifecycle check complete Markdown, deadline/budget and multiline explicit HTML anchor. |
| FE-A17 | Nested 40 randomized 12-node DAGs use independent graphlib.TopologicalSorter and shuffled declarations; raw preserved. Flat oracle evidence from R2 remains historical additional evidence. |
| FE-A18 | Full suite: 301 passed, 1 platform skip; spec/axis/manifest/source lifecycle gates; isolated installed wheel executes 22 CLI steps. Remote matrix pending, as stated above. |
| FE-A19 | Onboarding/flat route regressions, explicit-root nested README and isolated wheel sync/graph/explain/verify; FIELD_DEPENDENCIES distinguishes helper from installed API. |
| FE-A20 | Operation 128-field chain test succeeds with unchanged sys.getrecursionlimit. This is a regression in this environment, not a fixed supported-depth guarantee. |
| FE-A21 | Nested adoption test starts with the retained original v1 helper and populated receipts, upgrades helper with stable targets and unchanged old receipt bytes; explicit rename compatibility regression passes. |

### 10.3 Retained evidence and limits

Evidence is retained in [plan/evidence/FIELD_EXPANSION](evidence/FIELD_EXPANSION): full-suite output, isolated installed-wheel report, source lifecycle report and the release performance gate. The bundled wheel contains identical runtime Python bytes and README metadata to the source checkout. Its SHA256 is `3a307c7d1e45447cef8ec66aad93da8912cd7254a8e0774d650de188ae8c8c71`. Persisted state schema 1.0.0, machine envelope 2.0.0 and runtime layout 1.0.0 remain unchanged.

The existing performance gate passed for its 10,000-target / 50,000-edge graph/diff/render workload. It is not an end-to-end timing promise for a 10,000-field project. Recursive depth, current array shape/indices, cooperative tracked Python and lack of persistent cross-command values retain the agreed boundaries. Source/code changes abort a scope rather than silently restarting indefinitely.

Source/wheel version, current docs and generated MANIFEST are synchronized. The final patch is checked against the supplied baseline; remote branch/PR/tag/publication and bulk methodology migration remain deferred. No further user-owned decision was needed for implementation.

## 11. New-chat documentation review — 2026-10-07

The follow-up review checked the authoring route from Quickstart/WF06 through FIELD_DEPENDENCIES, runtime/model/CLI references and both fixtures. It found two actionable documentation gaps: the flat fixture retained its pre-expansion cache/top-level description, and “check does not rebuild” could be read as “check never executes builders,” despite current derived-source resolution.

The flat README and WF06 now describe stable-command reuse and independent nested APIs. FIELD_DEPENDENCIES adds a provider decision table, current readiness/array/atomic/depth scope and a diagnostic-to-recovery table. Quickstart and AI Usage Protocol route new sessions to these tables and explain how to reuse the helper, author explicit source/formula mappings and preserve input authority. Build Runtime distinguishes implemented P2/P3 responsibilities and supplies an explicit public BuildOperation library example with its transaction boundary.

Dependency/architecture/CLI/materialization references consistently distinguish in-memory source evaluation from recording a new build receipt and writing generated output. An empty `sync.data.rebuilt` list does not assert zero builder executions. Read-only commands retain their documented engine-state boundary. These are clarifications of tested dev23 behavior, not new runtime semantics or phase acceptance.

Only documentation and the generated inventory change in this follow-up. Runtime Python, packaging metadata, engine README and the active wheel are unchanged, so runtime build remains dev23 and wheel/source/README parity is retained. Verification uses the existing full suite and ordinary repository gates, local link/root checks and execution of the new library example against the real flat fixture. Previous section-10 test/package evidence remains historical; fresh follow-up results are recorded in the Review Log. Remote matrix and methodology migration are still outside this step.

Follow-up results: **301 passed, 1 skipped**; spec/axis audits, 677-file manifest validation and the 8-step source lifecycle pass. Changed local links and explicit project roots pass. The exact new Build Runtime code block executes against the flat fixture, returns A.g = 20 / B.g1 = 21, shares its operation with DependencyRuntime and preserves the project's file tree. No new runtime defect or user-owned blocking question was found.

## 12. Source coverage and known authoring errors — 2026-10-07

The user clarified that an actual dependency should be represented directly: when A uses a value owned by C that B's selected source does not supply, linking only to B is an incomplete source map. A should depend on C's exact value, or on a tracked derived B field that actually exposes it. An indirect derived-value route remains valid; redundant edges to every transitive prerequisite are not required.

The existing DAX01–DAX20 framework already contains DAX06 for capture/granularity, DAX07 for slice/comparison, DAX08 for invalidation and DAX09 for review agency. `docs/DEPENDENCY_AUTHORING_CHECKS.md` supplies a project-authoring catalogue DAE01–DAE06 mapped to those axes, with the A/B/C case, deterministic/semantic source routes and bounded verification guidance. AI Protocol, Quickstart, Dependency Model and Field Dependencies link the catalogue; Acceptance Axes explains its scope. These checks are used for new/changed connections rather than an obligatory full manual audit on every source edit.

The previous proposed general semantic-chain mechanism is not required to fix this incomplete-source example. A new propagation contract needs a real case that remains problematic after required sources/derived contracts are correctly declared. No new runtime status, transitive-review algorithm, schema or core behavior is introduced here. Runtime dev23 and the wheel are unchanged; the documentation inventory and cumulative patch are updated. Verification uses the existing documentation regressions, local links, specification/axis audits, manifest integrity and patch application; earlier full-suite evidence remains historical.
