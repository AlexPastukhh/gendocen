# Dependency Model

## 1. Dependency semantics live in project code

Canonical JSON stores data. Project code defines how that data affects other targets.

There are two different mechanisms.

### Deterministic/computational dependencies: actual tracked reads

```python
def build_price(ctx):
    price = ctx.read("resource://catalog/product#/price")
    tax = ctx.read("resource://catalog/tax_policy#/rate")
    return {"total": price * (1 + tax)}
```

The runtime creates dependency evidence from the values actually read through `BuildContext`. Project code does not separately maintain a deterministic source-edge table.

### Semantic/review dependencies: explicit rules

```python
def register(registry):
    registry.register(
        "file://architecture/rationale.md",
        [("resource://policies/method_policy#/allowed_methods", "set")],
        rule_id="architecture.rationale-method-policy",
        dependency_type="semantic_review",
    )
```

These rules say which changed context requires renewed judgment; they do not encode the judgment itself.

The declared source must cover what the consumer actually uses. A depends on C's exact value when B's selected field only points to C and does not expose that value; an indirect dependency is valid when B exposes the needed tracked derived field. Structural validity cannot detect every omitted assumption. Apply [Dependency Authoring Checks](DEPENDENCY_AUTHORING_CHECKS.md) when designing or changing a connection, especially DAE01/DAX06.

## 2. Dependency types and changed-state mapping

| Type | Meaning | Changed target state |
|---|---|---|
| `copy_reference` | deterministic copy/reference | `build_required` |
| `compute` | deterministic calculation | `build_required` |
| `aggregate` | deterministic many-input build | `build_required` |
| `semantic_review` | context change requires human/AI review | `review_required` |
| `compatibility` | compatibility/comparability requires review | `review_required` |
| `validity` | prior validity confirmation no longer applies | `stale` |

`invalid` is used when the runtime cannot safely establish a normal state (for example unavailable source/builder or incomplete audit evidence).

## 3. Granularity

Canonical executable v0.1 source refs support:

- field — `resource://x/y#/pointer`
- whole resource — `resource://x/y`
- whole plain file — `file://path.md`

Field dependency tracks only the addressed JSON Pointer value. Whole-resource dependency changes when any domain data in that resource changes.

Reading a field of a registered derived resource completes its owning builder. To demand independently computed nested fields, use [`FIELD_DEPENDENCIES.md`](FIELD_DEPENDENCIES.md): each atomic provider has its own internal whole target, and root/intermediate composites gather declared children. A leaf read leaves unrelated siblings unevaluated; a whole composite read requires all its declared descendants. Computed providers and optional raw overrides are explicit. This pattern uses the existing ref/receipt scheme.

Whole-file Markdown dependency does not require JSON. `file://` is for plain canonical Markdown; structured/derived content is addressed through `resource://` so canonical ownership and field-level tracking are not bypassed.

v0.1 intentionally does not address arbitrary Markdown sections. If another target depends on one part of prose, structure that part as addressable data or use whole-file semantic dependency.

## 4. Aggregation and collection membership

`aggregate` is supported, but v0.1 does not persist a first-class virtual `collection://...` identity. A builder records the exact refs it read.

When membership itself may change, make membership an addressable structured input:

```python
members = ctx.read("resource://indexes/documents#/members")
for member in members:
    ctx.read(f"resource://documents/{member}#/A")
```

Then adding a member changes the index dependency, triggers rebuild, and the new build captures the new member field dependency.

## 5. Receipt and baseline

After successful deterministic build or explicit semantic validation the runtime records a dependency receipt. Each entry points to the exact source ref, comparator, observed version and baseline snapshot.

Baseline stores only the dependency slice needed for later comparison:

- field dependency → field value;
- resource dependency → resource-domain value;
- whole-file dependency → file content/normalized representation.

The receipt is infrastructure evidence; project code does not hand-author it.

## 6. State transitions

Deterministic:

```text
VALID
  ↓ consumed input / builder revision changes
BUILD_REQUIRED
  ↓ explicit rebuild or sync
VALID
```

Semantic review:

```text
VALID
  ↓ semantic_review / compatibility source changes
REVIEW_REQUIRED
  ↓ external human/AI judgment
still-valid OR updated
  ↓ validate
VALID
```

Validity:

```text
VALID
  ↓ validity source changes
STALE
  ↓ external human/AI review
still-valid OR updated
  ↓ validate
VALID
```

A change is evidence that prior validation context changed. It is not an automatic proof that semantic prose is false.

## 7. `check`, `sync`, `rebuild`

`docengine check` compares active receipts/baselines with current inputs and may update dependency state/events. It can execute builders in memory to resolve current derived sources; it does not record replacement deterministic build receipts or materialize their outputs.

`docengine rebuild TARGET` explicitly executes one deterministic builder and advances dependency evidence for that target; it does not materialize configured views.

`docengine sync` performs a check, selectively rebuilds deterministic targets with no active receipt or `build_required`, checks again, materializes affected outputs, and reports unresolved semantic attention. `sync --all` broadens materialization selection; it does not force-rebuild every valid builder.

In dev23, CLI evaluation paths reuse each complete successful build within one stable operation, including sync's initial/final checks and materialization. Separate commands get fresh scopes. Persisted valid evidence can mean no target appears in `sync.data.rebuilt` even though current values were evaluated to compare dependencies. A successful cached value does not replace receipt/state/provenance validation.

## 8. Runtime state and history

```text
docs/_dependency/state/dependency_state.json
docs/_dependency/events/dependency_events.jsonl
docs/_dependency/receipts/...
docs/_dependency/baselines/...
```

Current state is mutable engine-owned runtime state. Events/history are append-only evidence. Normal workflows use CLI/runtime APIs rather than direct state-file editing.

## 9. Project-code revision

The current project extension revision is package-wide. Changing project Python can conservatively invalidate multiple deterministic targets through `builder_revision_changed`. Data dependency edges remain exact; code-revision invalidation is deliberately broader in v0.1.

## 10. Further runtime contracts

- `DEPENDENCY_RUNTIME.md` — persisted receipt/baseline/state/event details and comparators.
- `SEMANTIC_REVIEW.md` — review packets, context-token validation and explicit verdicts.
- `CORE_WORKFLOWS.md` — end-to-end authoring and invalidation workflows.
