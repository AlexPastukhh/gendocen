# Core Workflows

This document answers **what you can do with gendocen and how to do it safely**. A zero-context session should first complete [`CLEAN_CHAT_QUICKSTART.md`](CLEAN_CHAT_QUICKSTART.md), then jump directly to the relevant workflow below. Atomic normative behavior remains in [`USE_CASES.md`](USE_CASES.md); each workflow below references the relevant `DOCxx` contracts instead of redefining them.

The intended reader is a documentation author, developer, or AI agent that is allowed to edit project-owned documentation/data/code. The engine runtime itself is reusable infrastructure and is not the normal place for project-specific dependency logic.


## Task router

| Goal | Workflow |
|---|---|
| Adopt gendocen without converting everything | WF01 |
| Structure selected fields/resources | WF02 |
| Create a deterministic dependency / generated target | WF03 |
| Selectively recompute after deterministic input changes | WF04 |
| Review semantic prose after dependency changes | WF05 |
| Compose derived-of-derived | WF06 |
| Aggregate a changing set of resources | WF07 |
| Present the same object through multiple views / application boundary | WF08 |
| Diagnose state/provenance | WF09 |
| Regenerate/verify project reproducibility | WF10 |
| Recover interrupted mutation | WF11 |
| Migrate runtime layout | WF12 |

Do not read the entire document by default; a clean agent should use the quickstart to establish environment/root/trust/ownership, then read the workflow that matches the requested task.

For zero-context/project-authoring instructions in this document, `<root>` is the intended project selected during the quickstart. Copyable project commands keep `--project-root <root>` explicit rather than falling back to the caller's current working directory.

Workflow format follows the additive v0.36 scenario-template refinement: every WF declares **Actor**, **Goal**, **Atomic contract(s)**, a concise **Operational path**, and an **Observable result**. Complex authoring/review workflows may keep richer Starting state/Journey/Outcome sections; inspection/hardening workflows may use compact workflow-specific headings rather than artificial identical sections.

## 0. Mental model and project-owned editing boundary

Normal project authoring has three layers:

```text
human-facing documentation
  docs/<logical/path>.md

canonical structured documentation data
  docs/_structured/<logical/path>.json

project-owned executable semantics
  docengine_project/builders/<logical/path>.py
  docengine_project/dependency_rules/<logical/path>.py
```

The first two paths mirror the logical documentation tree. For deterministic generated targets, the builder code mirrors the **produced target**. Example:

```text
docs/catalog/price_with_tax.md
docs/_structured/catalog/price_with_tax.json
docengine_project/builders/catalog/price_with_tax.py
```

For a semantic dependency on a plain Markdown target:

```text
docs/architecture/rationale.md
docengine_project/dependency_rules/architecture/rationale.py
```

`docengine_project/` is deliberately outside `docs/`: documentation state and executable project semantics are different ownership domains. Ordinary project dependency authoring should not require edits to `src/docengine/**`.

### Before editing a visible Markdown file: determine ownership

A path ending in `.md` does **not** by itself tell you whether that file is canonical or generated. Before editing an existing file:

1. Run `docengine resources --project-root <root> --json`. Use it to distinguish plain documentation from managed/derived generated ownership.
2. If the target is managed/derived, inspect the mirrored descriptor under `docs/_structured/...` and edit canonical data or builder instead of the generated Markdown.
3. If `resources` reports the file as plain, run `docengine graph file://<logical/path>.md --project-root <root> --json`. A non-empty `rules`/`rule_edges` section means the plain Markdown is a semantic dependency target; inspect the mirrored rule before changing assumptions/dependencies.
4. If the file is plain and has no semantic rule, it is ordinary canonical Markdown.

Relevant contracts: **DOC02, DOC21**.

### Project Python is trusted code, not a sandbox

`docengine_project/**` is a clear extension boundary, but it is still normal Python. The runtime tracks cooperative dependency reads; it does not physically prevent a callback from calling `open()`, deleting files, using the network, or spawning a process. Structure and authoring discipline are the v0.1 protection. A future hard sandbox is not implied.

Even the `verify` command, while read-only with respect to engine-managed project state, may execute trusted project builders/validators/renderers for reproducibility checks. “Read-only” is therefore **not** a security promise about arbitrary project Python side effects.

## 1. Default AI authoring loop

For ordinary structured/project-code edits, use this loop:

```text
EDIT project-owned data/code
  ↓
docengine sync --json --project-root <root>
  ├─ deterministic missing/build_required targets → selective rebuild
  ├─ affected generated outputs → materialize
  └─ semantic review_required/stale → attention only, no semantic auto-fix
  ↓
for semantic attention:
  explain/diff → human/AI review → validate still-valid|updated
  ↓
docengine sync --json --project-root <root>
  ↓
docengine verify --json --project-root <root>
```

Use `docengine check --project-root <root> --json` separately when you want to inspect dependency changes **before** any deterministic rebuild. `check` can update dependency state/events, but it does not rebuild targets. `sync` already performs a check before planning selective rebuilds.

`sync --all` is **not** “force rebuild every valid builder.” Deterministic rebuild selection remains evidence-driven; `--all` broadens materialization to all registered views.

Relevant contracts: **DOC07, DOC15, DOC16**.

---

# Authoring and composition workflows

## WF01 — Adopt gendocen without migrating all Markdown

**Actor:** documentation author / AI agent  
**Goal:** start using the engine in an existing documentation tree without converting unrelated Markdown into JSON.  
**Atomic contracts:** **DOC01, DOC21**.
**Operational path:** initialize explicitly, inventory ownership, leave unrelated Markdown plain, then introduce structure only where needed.  
**Observable result:** plain Markdown remains canonical unless deliberately structured; gendocen can be adopted incrementally.

### Starting state

```text
project/
  docs/
    README.md
    architecture.md
    notes.md
```

These files can remain plain Markdown.

### Journey

1. Initialize the intended project explicitly with `docengine init --project-root <root> --json` or an equivalent explicit config.
2. Run `docengine resources --project-root <root> --json` to inspect the current inventory.
3. Leave plain documents plain until a concrete reason exists to structure them: machine-addressable fields, schema validation, deterministic composition, or generated views.
4. Introduce structured resources incrementally through WF02.

### Outcome

The engine coexists with ordinary Markdown. No mass migration is required.

### Engine does not do

- It does not require one JSON sidecar per `.md`.
- It does not automatically extract semantic structure from existing prose.
- It does not make plain Markdown non-editable.

---

## WF02 — Structure only the information that needs machine addressing

**Actor:** documentation author / AI agent  
**Goal:** make selected content addressable as fields/resources while keeping the rest of the repository Markdown-first.  
**Atomic contracts:** **DOC02, DOC04, DOC06, DOC21**.
**Operational path:** create an addressable managed structured resource and materialize its human-facing view.  
**Observable result:** selected fields become machine-addressable while the generated Markdown view is non-canonical.

### When to do this

Suppose other documents need stable access to:

```text
product.price
product.name
```

rather than “whatever text is currently under a heading in `product.md`.” Create a managed resource:

```text
docs/_structured/catalog/product.json
                    ↓ materialize
docs/catalog/product.md
```

Example descriptor/data:

```json
{
  "$docengine": {
    "resource_id": "catalog.product",
    "materialize": [
      {
        "renderer": "markdown",
        "path": "catalog/product.md",
        "path_base": "documentation_root"
      }
    ]
  },
  "data": {
    "name": "Example",
    "price": 100
  }
}
```

### Ownership change

Once `catalog/product.md` is a managed materialized view, the structured JSON is canonical. Do not hand-edit the generated Markdown as a substitute for changing `data`.

### v0.1 limitation

The future `promote` helper is not implemented. Today the structured resource is authored explicitly. See **DOC18** in the future section.

---

## WF03 — Build a derived document from exact structured fields/resources

**Actor:** project author / AI agent  
**Goal:** create a new object/document whose values are computed from raw/derived inputs, with exact dependency evidence.  
**Atomic contracts:** **DOC03, DOC04, DOC05, DOC06, DOC20**.  
**Operational path:** define a derived descriptor, author/register the mirrored builder, sync/rebuild, inspect captured dependencies, then materialize.  
**Observable result:** the derived target is reproducible from tracked inputs; raw sources remain unchanged and exact dependency evidence is recorded.
**Runnable fixture:** `examples/product_tax_project`.

This is the central deterministic authoring workflow.

### Example requirement

For a fresh project, first create A and B as valid structured resources (this is the WF02 resource shape). They do not need materialized views, so use an explicit empty `materialize` array:

`docs/_structured/example/a.json`:

```json
{
  "$docengine": {
    "resource_id": "example.a",
    "materialize": []
  },
  "data": {"field3": 10, "description": "A"}
}
```

`docs/_structured/example/b.json`:

```json
{
  "$docengine": {
    "resource_id": "example.b",
    "materialize": []
  },
  "data": {"field2": 5, "unrelated": "not used"}
}
```

We want derived C where:

```text
field1 = A.field3 + B.field2
```

The raw sources must stay unchanged. `field1` belongs to C, not to A or B.

### Step 1 — create the derived descriptor

For a materialized target `docs/example/c.md`, create `docs/_structured/example/c.json`:

```json
{
  "$docengine": {
    "resource_id": "example.c",
    "resource_kind": "derived_descriptor",
    "materialize": [
      {
        "renderer": "markdown",
        "path": "example/c.md",
        "path_base": "documentation_root"
      }
    ]
  },
  "data": {}
}
```

The descriptor owns target identity/path; its `data` is not a persisted cache of the builder result.

### Step 2 — create the mirrored builder module

Create:

```text
docengine_project/builders/example/c.py
```

Example:

```python
def build_c(ctx):
    # Whole-resource dependency if C intentionally reuses all of A.
    a = ctx.get("resource://example/a")

    # Field-level dependency: unrelated B fields do not invalidate C.
    b2 = ctx.read("resource://example/b#/field2")

    result = dict(a.to_builtin())
    result["field1"] = result["field3"] + b2
    return result


def register(registry):
    registry.register(
        "resource://example/c",
        build_c,
        builder_id="example.c",
        dependency_type="compute",
        comparator="exact",
    )
```

Use `ctx.get(resource)` only when changes anywhere in that resource should invalidate the target. Use `ctx.read(resource#/pointer)` for the narrow field/slice actually consumed.

### Step 3 — register the mirrored module

A Python file existing on disk is not enough. The project package must import/register it.

Recommended package structure:

```text
docengine_project/
  __init__.py
  builders/
    __init__.py
    example/
      __init__.py
      c.py
```

`builders/__init__.py`:

```python
from .example.c import register as register_c


def register(registry):
    register_c(registry)
```

project `docengine_project/__init__.py`:

```python
def register_builders(registry):
    from .builders import register
    register(registry)
```

For large repositories, each mirrored package can aggregate registrations from its children. The important invariant is that the target path tells the agent where to find its code **and** the registration path is explicit/testable. Confirm registration with an operation that actually loads/uses the extension: `sync`/`rebuild`, or `graph` while asserting `runtime_diagnostics` is empty. `resources` alone is inventory/ownership information and does **not** prove that a derived builder has been registered.

### Step 4 — build/sync

Normally:

```bash
docengine sync --json --project-root <root>
```

For an explicit single-target build:

```bash
docengine rebuild resource://example/c --json --project-root <root>
```

A successful deterministic build produces an in-memory `DerivedObject` and persists dependency evidence such as receipt/baseline/state/events. The DerivedObject payload itself is not a canonical persisted “derived object store.”

### Step 5 — inspect what was captured

Use:

```bash
docengine graph resource://example/c --json --project-root <root>
docengine explain resource://example/c --json --project-root <root>
```

Expected dependency evidence conceptually:

```text
resource://example/c
├─ whole resource://example/a
└─ field resource://example/b#/field2
```

### Step 6 — materialize

The renderer consumes the already-built object and formats it. It does not own `field1 = ...` computation.

```text
Derived C → renderer → docs/example/c.md
```

### Step 7 — prove invalidation and final project state

To complete the fresh-project authoring loop, change `B.field2` from `5` to `7`, then inspect before repair:

```bash
docengine check --project-root <root> --json
```

`resource://example/c` should become `build_required`. Repair and verify:

```bash
docengine sync --project-root <root> --json
docengine verify --project-root <root> --json
```

The rebuilt result has `field1 = 10 + 7 = 17`. Changing only `B.unrelated` must not invalidate C because the builder reads only `B#/field2`; WF04 develops these consumed-vs-unconsumed cases in detail.

### What not to do

Do **not**:

- read dependency-bearing JSON with `open()`, `Path.read_text()`, network/database calls, or hidden helper I/O instead of tracked `ctx.read/get`;
- copy `field1` back into raw A/B merely to avoid a builder;
- hand-maintain a deterministic “A depends on B” source-edge table when actual builder reads can capture it;
- put the computation into the Markdown renderer;
- edit generated `docs/example/c.md` as canonical content;
- modify `src/docengine/**` to add a project-specific dependency.

If an intentionally untracked escape hatch is ever used, it must be explicit and its reduced audit assurance must be accepted rather than pretending the dependency is tracked.

---

## WF04 — React to a deterministic upstream change

**Actor:** author / AI agent / CI  
**Goal:** detect a changed deterministic input and recompute only what is programmatically affected.  
**Atomic contracts:** **DOC07, DOC08, DOC09, DOC10, DOC11, DOC15, DOC17**.  
**Operational path:** change an upstream input, inspect with check when desired, then use sync for selective deterministic repair/materialization.  
**Observable result:** consumed changes produce build_required and selective recompute; unrelated unconsumed fields do not invalidate the builder dependency.
**Runnable fixture:** `examples/product_tax_project`.

### Case A — consumed field changes

Fixture builder reads:

```python
price = ctx.read("resource://catalog/product#/price")
tax_rate = ctx.read("resource://catalog/tax_policy#/rate")
```

Change `price: 100 → 125`.

Inspection-only path:

```bash
docengine check --json --project-root <root>
```

Expected target state:

```text
resource://catalog/price_with_tax → build_required
```

`check` does not update `price_with_tax.md`.

Repair path:

```bash
docengine sync --json --project-root <root>
```

`sync` checks state, rebuilds the missing/`build_required` deterministic target, rechecks, and materializes affected outputs.

### Case B — unrelated field changes

Change only:

```text
product.unused_note
```

The managed `product.md` view may need rematerialization because its own source changed, but the `price_with_tax` **builder dependency** should remain valid because it did not read `unused_note`.

This distinction is one of the main reasons to use field-level `ctx.read()`.

### Builder-code changes

v0.1 project extension revision is conservative/package-wide. Editing project Python can mark multiple deterministic builders `build_required` even if only one mirrored builder file was conceptually changed. This is safe over-invalidation, not proof that those builders share data dependencies. Per-builder code-revision precision is future optimization work.

### `sync --all`

Use `--all` when you want all registered views considered for materialization:

```bash
docengine sync --all --json --project-root <root>
```

It does not mean “ignore receipts and rebuild every valid deterministic builder.”

---

## WF05 — React to a semantic upstream change without automatic semantic repair

**Actor:** human / AI reviewer  
**Goal:** reevaluate prose/policy whose assumptions changed when correctness cannot be computed mechanically.  
**Atomic contracts:** **DOC03, DOC07, DOC09, DOC10, DOC12, DOC13, DOC14, DOC17**.  
**Operational path:** establish/inspect semantic attention, compare explain/diff evidence, edit prose only when judgment requires it, then validate explicitly.  
**Observable result:** semantic dependency changes remain review_required/stale until a human/AI records still-valid or updated; the engine does not auto-rewrite prose.
**Runnable fixture:** `examples/sample_project`.

Example rule path:

```text
docs/architecture/rationale.md
docengine_project/dependency_rules/architecture/rationale.py
```

The rule may declare that rationale depends on:

```text
resource://policies/method_policy#/allowed_methods
```

When allowed methods change:

```text
check/sync
→ rationale = review_required
```

The engine does **not** rewrite the rationale and does not decide that the old statement is false.

### Review flow

```bash
docengine explain file://architecture/rationale.md --json --project-root <root>
docengine diff file://architecture/rationale.md --json --project-root <root>
```

The human/AI compares target text with old/current dependency slices.

If still valid:

```bash
docengine validate file://architecture/rationale.md \
  --project-root <root> \
  --result still-valid \
  --reason "..." \
  --review-context <context-id> \
  --json
```

If update is required:

1. Edit the canonical semantic Markdown.
2. Validate with `--result updated`, reason and review context.
3. Run `sync`/`verify` again.

Semantic acceptance is an explicit judgment. `sync` intentionally leaves it unresolved.

---

## WF06 — Compose derived objects transitively

**Actor:** project author / AI agent  
**Goal:** allow a derived target to become a tracked input of another derived target.  
**Atomic contracts:** **DOC03, DOC05, DOC07, DOC11, DOC15, DOC20**.
**Operational path:** register an acyclic builder whose tracked inputs include another derived target, then let sync propagate deterministic effects transitively.  
**Observable result:** derived-of-derived provenance remains explicit and downstream targets are re-evaluated after upstream rebuilds.

Model:

```text
Raw A + Raw B → Derived C
Raw D + Derived C → Derived E
```

A builder for E obtains C through `BuildContext`, so the runtime can preserve a real dependency chain instead of copying values manually between JSON files.

When B changes:

1. C becomes `build_required`.
2. C is rebuilt.
3. E is re-evaluated/affected through its dependency on C.
4. `sync` performs bounded deterministic rebuild planning.

Deterministic cycles are rejected. Acyclic derived-of-derived composition is supported.

---

## WF07 — Aggregate many resources with explicit membership

**Actor:** project author / AI agent  
**Goal:** build one target from a changing set of structured resources, e.g. collect field `A` from ten documents.  
**Atomic contracts:** **DOC02, DOC03, DOC05, DOC07, DOC11, DOC15, DOC20**.
**Operational path:** make aggregate membership an addressable structured input and read both membership and member fields through BuildContext.  
**Observable result:** membership changes invalidate the aggregate and the next build captures the new exact member dependencies.

### Problem

Today:

```text
doc01#/A
...
doc10#/A
→ summary
```

Tomorrow `doc11` is added. If membership is discovered only by arbitrary directory scanning, the receipt may have no addressable dependency that says “the collection membership changed.”

### v0.1 pattern

Make membership itself a structured input:

```json
{
  "data": {
    "members": ["doc01", "doc02", "...", "doc10"]
  }
}
```

Builder:

```python
def build_summary(ctx):
    members = ctx.read("resource://indexes/documents#/members")
    values = []
    for member in members:
        values.append(ctx.read(f"resource://documents/{member}#/A"))
    return {"items": values}
```

Receipt conceptually contains:

```text
index#/members
doc01#/A
...
doc10#/A
```

Adding `doc11` to `members` invalidates the target; the next rebuild captures the new `doc11#/A` dependency.

### Limitation

v0.1 does not provide a first-class persisted virtual `collection://...` identity. “Collection” is conceptual aggregate semantics; explicit addressable membership is the reliable current pattern.

---

## WF08 — Present the same object through different views

**Actor:** project author / application integrator  
**Goal:** reuse the same raw/derived object while changing presentation.  
**Atomic contracts:** **DOC06, DOC22**.
**Operational path:** reuse the same raw/derived object through presentation renderers or an explicit application adapter boundary.  
**Observable result:** multiple views can share computation without making generated Markdown a query store or moving business logic into renderers.

Architectural model:

```text
Raw/Derived object
├─ Markdown renderer → managed file
├─ project-defined JSON renderer → managed file
├─ project-defined HTML renderer → managed file
└─ application/UI integration boundary
```

### v0.1 reality

Built-in support is file-oriented: built-in Markdown plus project-defined renderers that return text/bytes for managed outputs. The architecture allows other presentation surfaces, but gendocen core is not a ready-made live HTTP/UI backend.

If an application needs structured results, add an explicit adapter/projection boundary instead of parsing generated Markdown and instead of assuming rebuild persists a queryable DerivedObject payload store.

Renderers remain presentation-only; computation belongs in builders/pure helpers.

---

# Inspection and reproducibility workflows

## WF09 — Diagnose project state and provenance

**Actor:** author / AI agent / CI operator  
**Goal:** answer “what is affected, why, by exactly which input, and what happened before?”  
**Atomic contracts:** **DOC08, DOC09, DOC10, DOC17, DOC20, DOC21**.
**Operational path:** choose resources/status/graph/explain/diff/history according to the provenance question and prefer machine-readable output for automation.  
**Observable result:** the operator can identify ownership, current state, dependency edges, changed slices and historical evidence without conflating them.

Use the surfaces by question:

```text
resources  → what resources/views exist and who owns them?
status     → what are current target states?
graph      → what are upstream/downstream dependency edges?
explain    → why is this target in this state?
diff       → which validated slices changed and how?
history    → what receipts/events/reviews led here?
```

For AI operation, prefer `--json` and inspect stable refs/IDs rather than parsing human prose.

The dependency graph is not the same as the project's domain/object graph. It is runtime evidence of build/review dependencies.

---

## WF10 — Clean-regenerate and verify reproducibility

**Actor:** CI / release operator / AI agent  
**Goal:** prove generated views can be recreated from canonical inputs/code and detect drift/missing outputs.  
**Atomic contracts:** **DOC06, DOC16, DOC22**.
**Operational path:** materialize/regenerate the required views, then verify project reproducibility and inspect any drift/attention.  
**Observable result:** generated outputs are reproducible from canonical inputs/code, while drift, missing outputs or semantic attention are reported rather than silently repaired.

Typical flow:

```bash
docengine materialize --all --json --project-root <root>
docengine verify --json --project-root <root>
```

or, when deterministic dependency state also needs repair:

```bash
docengine sync --all --json --project-root <root>
docengine verify --json --project-root <root>
```

`verify` reports a complete project-level audit and does not repair engine-managed state. It may nevertheless execute trusted project callbacks to test current builders/renderers. Those callbacks are ordinary unsandboxed Python; do not treat `verify` as a security boundary for untrusted project code.

Removed generated targets are not silently deleted. Orphan ownership is surfaced and resolved explicitly according to the materialization contract.

---

# Operations / hardening workflows

## WF11 — Recover an interrupted mutating transaction

**Actor:** operator / AI agent acting under explicit recovery policy  
**Goal:** reconcile a crash without guessing or overwriting unknown post-crash changes.  
**Atomic contract:** **DOC23**.
**Operational path:** detect recovery_required, inspect the interrupted transaction, run non-force recovery first, and use force only as an explicit destructive decision.  
**Observable result:** recognized interrupted mutations are reconciled without overwriting unknown post-crash changes by default, with recovery actions audited.

Normal flow:

```text
mutation crashes
→ open transaction journal remains
→ normal mutation is blocked / verify reports recovery_required
→ inspect
→ docengine recover --project-root <root> --json
```

Default recovery validates the complete journal and current bytes before mutation. If a target contains unknown post-crash bytes or an unexpected deletion, recovery stops without overwriting that external change.

Only an explicit operator decision may use:

```bash
docengine recover --force --json --project-root <root>
```

`--force` is destructive intent, is never automatic, and is recorded in recovery audit history.

---

## WF12 — Migrate runtime layout safely

**Actor:** operator / AI agent  
**Goal:** move recognized persisted runtime evidence to the current layout without resetting released provenance.  
**Atomic contract:** **DOC24**.
**Operational path:** run the registered migration for a recognized persisted layout and validate preserved evidence/audit output.  
**Observable result:** recognized state moves to the current runtime layout without inventing/resetting unknown provenance; unsupported/corrupt layouts fail closed.

Explicit command:

```bash
docengine migrate --json --project-root <root>
```

The migration runtime:

1. identifies a recognized source layout;
2. validates released evidence;
3. executes only a registered migration path;
4. preserves released receipt/baseline/state/event bytes when the migration contract says so;
5. records layout marker + migration audit event.

Unknown/future/corrupt layouts are not guessed or reset.

---

# Future authoring helpers

## FWF01 — Promote plain Markdown to a managed structured resource

**Atomic contract:** **DOC18** (`implementation_target=future`).

Desired future convenience:

```text
plain docs/foo.md
→ explicit promote helper
→ docs/_structured/foo.json becomes canonical
→ docs/foo.md becomes a generated/managed view
```

The helper must establish clear ownership and parity without forcing unrelated Markdown into structured form. This helper does not exist in v0.1; WF02 describes the current explicit/manual authoring path.

## FWF02 — Demote a managed resource back to plain Markdown

**Atomic contract:** **DOC19** (`implementation_target=future`).

Desired future convenience:

```text
managed structured resource
→ check downstream dependencies / export policy
→ explicit demote helper
→ human-readable docs/foo.md becomes canonical plain Markdown
```

The helper must not silently break downstream structured dependencies and must preserve an ownership-change audit trail. It is not a v0.1 command.

---

# Quick anti-pattern index

These are common ways to make the engine look configured while defeating its guarantees:

| Anti-pattern | Why it fails |
|---|---|
| Editing `src/docengine/**` for one project's dependency | turns project semantics into an engine fork; normal authoring belongs in `docengine_project/**` |
| Creating mirrored builder file but never registering/importing it | file exists, but engine has no builder for the descriptor target |
| Direct `open()`/network/database read for a dependency-bearing input | source is absent from tracked receipt, so invalidation can be wrong |
| Copying computed values into raw canonical JSON | creates duplicated truth and bypasses provenance/recompute |
| Editing generated Markdown as canonical | next materialization overwrites it or verification reports drift |
| Computing dependency-derived values in renderer | hides computation from build dependency/provenance and couples it to one presentation |
| Treating `check` as rebuild | state may become `build_required`, but output remains unchanged |
| Treating `sync --all` as force-rebuild-all | rebuild selection is still evidence-driven; `--all` broadens materialization |
| Treating semantic `review_required` as automatically fixable | engine can prove context changed, not which new prose is semantically correct |
| Treating project Python/`verify` as sandboxed | callbacks are trusted cooperative Python and can have arbitrary side effects |

