# P3 Dependency Runtime

## Purpose

P3 turns P2 tracked reads into persistent, explainable dependency state without making semantic judgments.

The runtime records **what a target was built/validated against**, detects later structural changes, produces typed diffs and updates operational state.

It does **not** decide whether prose remains semantically correct. That review workflow belongs to P4.

## Storage

All dependency-runtime persistence lives under the documentation root:

```text
docs/_dependency/
  baselines/
    sha256-<digest>.json
  receipts/
    receipt-<digest>.json
  state/
    dependency_state.json
  events/
    dependency_events.jsonl
```

The runtime does not store this state inside the engine package or project code.

### Baselines

Baselines are content-addressed normalized dependency slices.

- structured field dependency → only that field value;
- whole structured resource → canonical domain `data`, never `$docengine` metadata;
- plain Markdown `file://` dependency → full text normalized only for line endings when using `text_unified`;
- unrelated upstream content is not copied into the baseline.

P3 persists only currently canonical-addressable source granularities: `field`, `resource`, and `whole_file`. Aggregate builders record multiple exact refs; virtual field-set/collection addressing is not invented in v0.1.

Baseline blobs include `state_schema_version` and are addressed as:

```text
baseline://sha256/<digest>
```

### Receipts

A `DependencyReceipt` points from a target to the exact baselines against which it was successfully built or explicitly recorded.

For explicit review/validation receipts, P3 also pins `target_revision`: the exact revision of the target that was reviewed. Editing the target itself after validation makes that receipt no longer current even when all upstream dependencies are unchanged. A missing target is `invalid`; an edited semantic target returns to `review_required` (or the dependency-type-specific non-valid state).

Builder receipts also contain:

- `builder_id`;
- package-wide `builder_revision`;
- `output_digest`;
- `audit_complete`.

Receipt IDs are deterministic hashes of the stable receipt content. Retrying the same record operation does not create divergent receipts.

### State

`dependency_state.json` stores only current operational state:

- `valid`
- `stale`
- `review_required`
- `build_required`
- `invalid`

`stale` or `review_required` never means the engine has proved content false. It means current validity is no longer confirmed against the current upstream state.

### Events

`dependency_events.jsonl` is append-only history. Each persisted state mutation advances a monotonic project-level `state_revision`; new events include that revision in their stable `event_id`. Exact retries do not append a duplicate because the state no longer changes, while a later re-activation of an older content-stable receipt is still recorded as a new event occurrence.

P7 will add stronger locking/transaction recovery. P3 guarantees confined writes, atomic replacement for JSON state/receipts/baselines, and append-only event semantics.

## Comparators

P3 v0.1 provides:

- `exact`
- `json_structured`
- `sequence`
- `set`
- `text_unified`

Comparator IDs are validated when a dependency is persisted.

Markdown semantic/AST comparison is intentionally deferred.

## Change classification

When a dependency slice changes:

| Dependency type | P3 state |
| --- | --- |
| `copy_reference` | `build_required` |
| `compute` | `build_required` |
| `aggregate` | `build_required` |
| `semantic_review` | `review_required` |
| `compatibility` | `review_required` |
| `validity` | `stale` |

If a required source/builder is unavailable, state is `invalid` rather than pretending a normal comparison succeeded.

If P2 provenance is `audit_complete=false`, the receipt may be retained for diagnostics but the target is not marked `valid`.

## Builder-code invalidation

Builder logic lives in code, so data-only dependency tracking is insufficient.

P3 persists P2 `builder_revision`. If the project Python package revision changes while data inputs remain identical, deterministic targets become `build_required`.

The v0.1 revision is package-wide by design. This may over-invalidate, but it must not miss helper-code changes.

## Query/command boundary

Implemented through P4:

```text
docengine status
docengine check
docengine diff TARGET
docengine explain TARGET
docengine history TARGET
docengine graph [TARGET]
docengine validate TARGET --result still-valid|updated --reason ... --review-context ...
```

- `status`, `diff`, `explain`, `history`, `graph` are read-only.
- `check` may update dependency state/events but never canonical content or validated baselines.
- `validate` is the official semantic-review mutation: it requires a fresh review context, explicit decision and reason, then advances the validated semantic receipt/event trail.
- read-only commands do not create `_dependency` merely by inspecting a project.

All commands support `--json` for AI/CI usage.

## Integrity

The programmatic runtime exposes integrity checks connecting:

```text
state → active receipt → baseline
history/event → receipt
state/event changed_dependencies → sources recorded by that receipt
receipt comparator → comparator registry
```

Missing/corrupt baselines, wrong receipt hashes/types, state pointing at missing/wrong-target receipts, target mismatches, or state/events claiming dependency changes absent from their receipt are detected rather than silently ignored. Persisted audit-critical fields are validated strictly; malformed JSON values are not coerced into apparently valid evidence.


## P4 semantic receipt extension

Semantic validation receipts additionally persist `semantic_rule_id` and `semantic_rule_revision`. `check` compares the current project-code rule revision to the validated receipt and returns the dependency-type-specific non-valid status when the rule changes. Semantic validation events carry the explicit review context, decision, reason, actor metadata and evidence trail. See `SEMANTIC_REVIEW.md`.
