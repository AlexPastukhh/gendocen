# Field Dependencies — project-owned field/path pattern

Use this guide after the environment/root/trust/ownership preflight in [`CLEAN_CHAT_QUICKSTART.md`](CLEAN_CHAT_QUICKSTART.md), when WF06 requires dependencies between independently computed fields of different documents.

**Actor:** project author / AI agent.
**Goal:** compute a field from raw or computed fields without completing every field of the source document first.
**Atomic contracts:** DOC03, DOC05, DOC07, DOC11, DOC15, DOC20.
**Operational path:** declare providers, register small internal resources, compose final documents, then sync and verify.
**Observable result:** an acyclic field graph works even when final documents refer to each other's fields; actual computation cycles remain errors.

This is a copyable **project helper**, not a native field-target API or persisted ref scheme. The bundled runtime is `0.1.0.dev25`. The implementation and executable fixture are in [`examples/field_dependency_project`](../examples/field_dependency_project/README.md).

The nested counterpart is [`examples/nested_field_project`](../examples/nested_field_project/README.md). Contracts and acceptance are recorded in [`FIELD_DEPENDENCY_EXPANSION.md`](../plan/FIELD_DEPENDENCY_EXPANSION.md). The helper remains project-owned; the installed engine supplies `BuildOperation`, not `docengine.FieldPlan`. Recursive execution and the normal recursion limit are unchanged.

For a field sourced from ordinary canonical Markdown, use the copyable [`examples/markdown_field_project`](../examples/markdown_field_project/README.md): tracked whole-file read → author-selected bounded derived field → independent nested provider → generated quotation. Its selected-section and whole-file semantic rules show which edits actually require review. Source meaning/bounds belong to the author; missing/duplicate/inverted bounds fail explicitly. Original prose stays Markdown; HTML anchors survive rendering but do not register dependencies by themselves.

This route is implemented and locally accepted on Linux/Python 3.12. The remote Ubuntu/Python 3.11 and Windows/Python 3.14 matrix remains unexecuted for the extension; fresh evidence is in the acceptance record. Independent fields may occur at any object nesting, subject to the existing recursion limit. Arrays use existing indices/shape; dynamic membership belongs to raw data or one atomic provider. For a whole object produced by one function, reading a child completes that function. To make children independent, declare separate child providers and compose their parent.

## 1. Document references and computation cycles are different

Example:

| Logical field | Provider |
|---|---|
| `A.a` | required `resource://inputs/A#/a` |
| `B.b1` | required `resource://inputs/B#/b1` |
| `C.x` | required `resource://inputs/C#/x` |
| `B.a1` | optional raw `inputs/B#/a1`; otherwise `C.x * 2` |
| `A.g` | `B.a1` |
| `B.g1` | `A.g + 1` |

Both documents reference the other document, but evaluation has a valid order: `B.a1`, `A.g`, `B.g1`. A single builder per final document can falsely recurse: reading B.a1 first builds all B, including B.g1, which then needs the in-progress A. Reordering assignments inside B does not publish its partial result to the engine.

Use independent computational units for independent fields. The simpler case where B.g1 uses raw A.a also works: its producer can call `fields.read(ctx, "A", "a")` instead. A real cycle `A.g -> B.g1 -> A.g` still has no initial value and is rejected. Ordinary Python control flow inside a producer remains available; this recipe does not invent fixed-point semantics for circular definitions.

## 2. Find the canonical source before choosing a formula

Raw inputs and derived outputs have separate identities:

```text
docs/_structured/inputs/A.json  -> canonical raw inputs.A
docs/_structured/views/A.json   -> metadata-only derived descriptor views.A
docengine_project/builders/views/A.py -> complete derived views.A
docs/views/A.md                 -> materialized human view
```

The descriptor's `data: {}` is not an unfinished raw A. It identifies the output and its materialization; actual output values come from builders. Do not read a descriptor as raw input, copy computed values into raw JSON, or use generated Markdown as a data query store.

Before editing an existing project, identify its real source mapping and inspect registered code. Do not infer provider ownership from filenames alone. When no helper exists, copy the reference helper into the project package and declare its sources; when a helper is already present, reuse its API and declarations.

Check source coverage before choosing a dependency: a related field that only refers to another owner does not supply that owner's value. If A uses C's period and B's selected prose only says "consult C", A needs C's exact field or a tracked derived B field exposing the period. Do not add every transitive prerequisite redundantly when the selected derived value already supplies what A uses. See [DAE01 and the other Dependency Authoring Checks](DEPENDENCY_AUTHORING_CHECKS.md).

## 3. Ready-made project helper and author-owned code

Copy [`docengine_project/fields.py`](../examples/field_dependency_project/docengine_project/fields.py) into the project's own package. It uses only public `BuilderRegistry`, `BuildContext`, `ResourceRef` and object APIs.

| Surface | Responsibility |
|---|---|
| `fields.py::FieldPlan` | provider lookup, tracked routing, explicit override policy and view composition |
| `field_plan.py` | logical document/field to canonical source or producer mapping |
| `builders/fields/<target>.py` | formulas for individual fields; target-oriented internal resource placement |
| `builders/views/<document>.py` | complete composed output for materialization |
| package `register_builders(registry)` | activate the field plan and final builders |
| engine runtime | recursive builds, cycle detection, stable-operation reuse, receipts, invalidation, sync and materialization |

The helper does not invent formulas, inspect arbitrary files, manipulate engine state, or maintain a second value cache. It is not installed as `docengine.FieldPlan`; it belongs to the project. Ordinary authors/AI write declarations and producers and use the prepared helper. Generic helper changes remain explicit project-code changes; they do not require changing `src/docengine/**`.

### Choose the provider before writing a formula

| Project contract | Declaration / read |
|---|---|
| A required value belongs to canonical raw JSON | `input` / `input_path`; absence is a required-source error. |
| A value always comes from a formula | `computed` / `computed_path` with a unique internal target and a producer. |
| A canonical raw value may override a formula | `computed` / `computed_path` with a matching explicit `raw_override`; presence selects raw, absence selects the producer. |
| One formula returns an object/array as one computational unit | Declare one atomic provider; read its child path through `read_path`. |
| Children of an object must compute independently | Bind its document with `document`, declare independent child paths, then use `read_path` for leaves and `compose`/whole-composite reads for completed objects. |
| A raw value is absent and no producer is declared | Inspect the source map and determine the intended input/formula from project requirements. Do not infer a fallback from a descriptor or generated Markdown. |

Legacy names are literal: `computed("A", "plan.budget", ...)` owns the single key `plan.budget`; `computed_path("A", "/plan/budget", ...)` owns the nested key. Do not reinterpret old names when adopting the helper. Bind canonical documents before `register`, and register both the plan and final views. Producers read logical fields through the helper; final-view builders gather the finished values.

AI authors reuse `fields.py` and implement the source map, formulas, registrations and views in project code. Follow the existing project contract when choosing input authority; an ownership error alone is not a reason to add a raw override. Engine receipts/state are maintained through runtime commands. Extend generic helper/core behavior only as an explicit maintenance task, rather than changing it to conceal an unavailable required input.

## 4. Declare one provider for each field

The runnable fixture's `field_plan.py` imports its mirrored producers and declares:

```python
FIELDS = FieldPlan()
FIELDS.input("A", "a", "resource://inputs/A#/a")
FIELDS.input("B", "b1", "resource://inputs/B#/b1")
FIELDS.input("C", "x", "resource://inputs/C#/x")
FIELDS.computed("B", "a1", "resource://fields/B_a1", produce_b_a1,
                raw_override="resource://inputs/B#/a1")
FIELDS.computed("A", "g", "resource://fields/A_g", produce_a_g)
FIELDS.computed("B", "g1", "resource://fields/B_g1", produce_b_g1)
```

Provider rules:

- `input(...)` always reads its declared field ref. An absent required field is an error; it never searches a derived document or guesses a producer.
- `computed(...)` uses a distinct whole internal resource target. The producer receives `(ctx, fields)` and returns one JSON-compatible value. The helper wraps it as `{"value": ...}` because current engine builder outputs must be objects/arrays.
- `raw_override=...` explicitly gives a present canonical raw field precedence. Absence invokes the producer. A present `null`, `false` or `0` remains a supplied value; it is not absence.
- Duplicate logical providers and shared computed targets are rejected. Finish declarations before registration.
- Computed values in raw inputs are rejected by `compose()` unless the matching override is declared. A stale generated value must not silently become authoritative input.

The earlier generic recipe "if any field is missing, read it from the derived object" is insufficient: a missing required raw A.a has no producer. Falling back to a whole A builder can report a false cycle instead of a missing input. This helper applies fallback only where a producer and override policy are declared.

## 5. Write producers against the field helper

```python
# builders/fields/B_a1.py
def produce(ctx, fields):
    return fields.read(ctx, "C", "x") * 2

# builders/fields/A_g.py
def produce(ctx, fields):
    return fields.read(ctx, "B", "a1")

# builders/fields/B_g1.py
def produce(ctx, fields):
    return fields.read(ctx, "A", "g") + 1
```

`fields.read(ctx, "B", "a1")` resolves the small internal `resource://fields/B_a1#/value`. It does not build final B or evaluate its unrelated g1 first. Internal resources need no descriptor JSON or Markdown file. Their identities and tracked reads appear in the dependency graph/receipts; `resources` catalogs documentation-owned resources and therefore is not their registration proof.

Do not replace these reads with `ctx.read("resource://views/B#/a1")` inside a field producer: that still asks the current engine to build the entire final B. Do not access private `_session` internals or partly built objects. Direct `registry.register("resource://views/B#/a1", ...)` is not supported by v0.1.

Use ordinary `ctx.read()` for additional exact resource/file dependencies that are not logical fields in the plan. All dependency-bearing reads, including helper reads, must stay tracked.

## 6. Register producers and compose complete documents

Package registration must load both layers. Merely placing producer modules in the mirrored directory does not activate them:

```python
def register_builders(registry):
    from .field_plan import FIELDS
    from .builders import register
    FIELDS.register(registry)
    register(registry)
```

Import the final view modules inside `builders.register()` so importing field producers does not create a Python import cycle with `field_plan.py`. A Python import cycle is distinct from a dependency computation cycle.

Final A builder:

```python
from ...field_plan import FIELDS

def build(ctx):
    return FIELDS.compose(ctx, "A", "resource://inputs/A")

def register(registry):
    registry.register("resource://views/A", build, builder_id="views.A")
```

`compose()` copies raw fields into a private working dictionary and resolves declared fields before returning the complete view. Required inputs are checked through their declarations. The engine freezes the successful result; the helper never publishes a mutable partial document or writes computed values back to canonical input JSON. Final documentation-owned targets still need derived descriptors and normal materialization metadata.

## 7. Dependency granularity, invalidation and cache boundaries

- A required input read captures its exact field ref.
- A computed field consumer captures the internal resource's exact `#/value` slice. That field's own receipt records its prerequisites.
- Optional raw override selection uses tracked `ctx.get()` on the whole raw input. This records both presence and absence of the override. An unrelated change in that raw object can therefore reevaluate this producer; it is conservative dependency capture.
- `compose()` uses whole raw data because it preserves all raw fields in the output. Changes to copied fields legitimately affect the final view.
- The fixture's C.unused_note is neither consumed nor copied into A/B, so changing it does not require their deterministic rebuild.
- A source change can rebuild an intermediate producer without changing its value. Consumers need reevaluation against that value and may remain valid when their exact consumed slice is unchanged.
- CLI commands that evaluate builders share a stable-operation cache across resolution, checks, rebuilding and materialization. Each successful target executes once within that command. Separate commands evaluate current inputs again; no field-value cache is persisted. Standalone BuildEngine calls remain fresh unless the caller explicitly supplies a shared BuildOperation.
- Project Python revision remains package-wide: editing helper/declaration/producer code can mark multiple deterministic targets `build_required`.

Keep producers deterministic and free of hidden dependency-bearing I/O. Do not solve repeat execution with an unversioned global cache; persisted reuse requires current input/code evidence. CLI commands capture each used input once and validate its actual bytes and project code at completion. Keep canonical inputs/code stable until the command finishes. A final mismatch produces a domain failure and transaction rollback preserves prior engine-managed outputs/evidence; a temporary edit fully restored before validation need not be observed. This cooperative contract still requires tracked producer reads. See [command snapshots](BUILD_RUNTIME.md#command-snapshots-dev25).

`check`, `diff`, `explain` and `verify` can execute current builders in memory to resolve derived sources. The CLI term `rebuild` means recording the selected target's new build evidence; `sync.data.rebuilt` lists those evidence-advancing rebuilds. An empty list therefore does not prove that source builders were never evaluated. Inspection retains its documented state/output mutation boundary, while successful in-memory results are reused within the command.

## 8. New-chat completion route

After adapting the source map, formulas, registration and output descriptors:

```bash
docengine sync --project-root <root> --json
docengine graph --project-root <root> --json
docengine explain resource://views/A --project-root <root> --json
docengine verify --project-root <root> --json
```

Require empty runtime registration diagnostics and expected field-resource edges. In a copied fixture, test each of these before claiming the recipe works:

1. Initial C.x = 10 gives A.g = B.a1 = 20 and B.g1 = 21.
2. Changing C.x to 12 gives 24/25 after sync.
3. Changing only C.unused_note does not require deterministic rebuild.
4. Adding raw B.a1 = 99 gives 99/100 and removes the C.x read from B.a1's active evidence.
5. Changing C.x while the override is present leaves outputs unchanged.
6. Removing the override uses current C.x again.
7. Missing required A.a produces a missing-input error; an undeclared field produces a provider error, never inferred fallback.
8. A real circular pair of producers is rejected; map internal resource names back to logical fields through `field_plan.py`.

Never edit `_dependency` receipts/state or generated Markdown to make a check pass. Use the registered builder source, normal sync/rebuild and explicit semantic review routes.

## 9. Values, Markdown anchors and current limits

Legacy `input`, `computed` and `read` names remain literal top-level keys, including dots, `/` and `~`. Use the explicit path APIs below for nested fields. Values can themselves be atomic objects/arrays; reading inside one completes that provider. Parallel scheduling, implicit sparse array construction and persistent reuse are not helper APIs. All JSON Pointer tokens use `~0` for literal `~` and `~1` for literal `/`.

For the built-in Markdown renderer, a multiline string value can contain an explicit anchor and heading, for example `<a id="a-g"></a>\n## G\n...`. Merely adding an `anchor` scalar field does not instruct the renderer to create an HTML anchor. Markdown links/anchors are navigation; tracked `resource://...#/field` reads establish computational dependencies. A custom renderer must preserve or deliberately implement the project's anchor presentation policy.

Native field-target registration, cross-command value reuse and changes to persisted field evidence remain future engine decisions. Their absence does not require changing core for the demonstrated field-resource pattern. See [`BUILD_RUNTIME.md`](BUILD_RUNTIME.md), [`CODE_MODEL.md`](CODE_MODEL.md) and the runnable fixture for the current accepted boundaries.


## 10. Independent nested fields and complete objects

Bind each document's canonical raw source before registration. Path arguments are ordinary JSON Pointers (not URI fragments or dotted labels):

```python
FIELDS.document("A", "resource://inputs/A")
FIELDS.document("C", "resource://inputs/C")
FIELDS.computed_path("A", "/plan/deadline", "resource://fields/A_deadline", deadline)
FIELDS.input("C", "rate", "resource://inputs/C#/rate")
FIELDS.computed("C", "total", "resource://fields/C_total", total)
FIELDS.computed_path("A", "/plan/budget", "resource://fields/A_budget", budget,
                     raw_override="resource://inputs/A#/plan/budget")
```

The deadline producer reads a calendar field. The estimate producer reads `fields.read_path(ctx, "A", "/plan/deadline")` and C.rate. Budget reads C.total. A deadline request never waits for budget or completes plan. `read_path(ctx, "A", "/plan")` assembles its required children plus preserved raw members. `compose(ctx, "A")` assembles the root; `compose(ctx, "A", path="/plan")` assembles an intermediate object.

Use `input_path` for an explicitly owned required nested source. An undeclared leaf has no guessed producer; copied raw members are preserved but should be declared or read directly through ctx when used as individual prerequisites. Root/composite declarations and their internal targets are generated from bound documents and provider ancestors. Internal object targets use stable IDs; `FIELDS.describe()` maps those IDs to logical paths for graph/cycle diagnostics.

An atomic provider owns its entire subtree. Declaring a provider for `/plan` and another for `/plan/deadline` is rejected. Bind raw input as the composition base instead if children need independent producers. Reading the whole plan from budget demands budget itself and correctly reports a cycle.

Missing intermediate objects can be created privately; an existing scalar/null ancestor is a shape conflict. Objects inside existing arrays are addressable, for example `/tasks/0/finish`; indices must exist and use the current array shape/order. Numeric tokens under objects are literal keys. Array membership is owned by raw data or one atomic array producer. Null/false/zero/empty leaf overrides remain authoritative. Registering a nested override against a different raw binding is rejected.

Bound computed providers capture the whole raw document to enforce absence/ownership; this can conservatively reevaluate them after unrelated raw changes. This is documented tracking, not a promise of the smallest possible rebuild set. Consumers still track exact internal value slices.

## 11. Existing projects and identity changes

Copy the extended helper while retaining existing explicit field target IDs. Code revision changes are expected to refresh receipts; old receipts/history remain intact. Literal old labels retain their meaning.

If a path rename changes an inferred object target, retain an explicit compatibility builder for its old ID instead of deleting dependency state. For example, after moving `/plan` to `/execution` and updating producers/raw data:

```python
old = FIELDS.object_target("A", "/plan")
new = FIELDS.object_target("A", "/execution")
registry.register(old, lambda ctx: ctx.get(new).to_builtin(),
                  builder_id=f"object:{old.logical_resource_id}", dependency_type="aggregate")
```

Register this after FIELDS.register. The old whole internal resource remains available and delegates to the new complete value. Existing logical producer reads must be updated deliberately; compatibility IDs do not reinterpret old path labels. For removal, retain an explicit compatibility/provider contract while consumers or active receipts still require it. No automatic receipt/history erasure is introduced.

## 12. Errors, recovery and operation boundaries

A missing required direct/transitive source, a failed producer or genuine cycle produces the normal domain failure. Check classifies unavailable dependencies invalid; sync does not materialize invalid results. Restore data/code, then run sync and verify. Do not edit state or Markdown to hide failures.

Status/history/graph describe persisted state; verify checks current validity read-only. Failed producers publish no ready value and may be retried in a fresh operation. Stable-operation reuse preserves branch reads, provenance, receipt activation and state/events, including equal-value override switches.

| Diagnostic / observation | Recovery |
|---|---|
| `required input ... is missing` | Restore the required canonical source/key or correct its declared ref; a missing input does not select an undeclared formula. |
| `no declared provider` / registration diagnostic | Correct the source/provider map and package registration, then inspect graph diagnostics. |
| `raw field conflicts with computed` | Resolve ownership in canonical data/declarations. Declare a matching override only if raw input is intended to have authority. |
| `container shape conflict` / `invalid array index` | Correct the raw container or path. Existing scalar/null ancestors and absent array indices cannot host independent child insertion. |
| Deterministic cycle path | Map internal IDs with `FIELDS.describe()`; remove the circular demand. A child asking for its own whole parent is a real cycle. |
| `source changed` / `build_sources_changed` | Stabilize the consumed data/project code and retry a fresh command. CLI transaction rules preserve prior engine-managed outputs/evidence. |
| Old internal target unavailable after a rename | Retain the old ID through the explicit compatibility builder in section 11; update logical reads deliberately. |
| `maximum recursion depth exceeded` | Treat this as execution depth exhaustion. Keep the accepted depth policy and revisit the executor only for a real project exceeding it; do not label it a graph cycle. |

After correcting the cause, run sync and verify with the same explicit project root. Generated Markdown and `_dependency` files are not repair inputs.

Library callers can create `BuildOperation(catalog, registry)`, pass it as `operation=` to BuildEngine and DependencyRuntime, and call `assert_current()` before externally publishing work. Never share an operation between different catalogs/registries or commands. BuildOperation is an in-memory consistency/cache scope; library callers must arrange the existing lock/transaction guards for their writes. CLI manages this scope and transaction integration itself. There is no persistent cache or automatic recursion-limit increase.
