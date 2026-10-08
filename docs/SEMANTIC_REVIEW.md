# P4 Semantic Review and Validation Contract

## Purpose

P4 lets project code declare **semantic dependencies** while keeping the semantic judgment outside the engine.

The engine may prove that a validated dependency/target/rule context changed. It must **not** decide that prose or policy is now semantically wrong. A human, AI or CI actor explicitly records one of two outcomes:

- `still-valid` — the current target content remains semantically valid against the reviewed current dependency state;
- `updated` — the target was edited and the edited current target is now valid against the reviewed current dependency state.

Both outcomes require a non-empty reason.

## Project-owned semantic rules

Semantic dependency semantics live in the configured project package, not in canonical documentation JSON.

The project package may expose:

```python
def register_semantic_dependencies(registry):
    registry.register(
        "file://architecture/rationale.md",
        [("resource://policies/method_policy#/allowed_methods", "set")],
        rule_id="architecture.rationale-method-policy",
        dependency_type="semantic_review",
    )
```

Supported semantic dependency types in v0.1:

- `semantic_review`
- `compatibility`
- `validity`

A rule has a deterministic revision derived from its target, type, exact sources and comparators. A rule revision change invalidates prior semantic confirmation. Rule-type changes are classified using the **current** rule type rather than the dependency type stored in the previous receipt; this prevents a `semantic_review → validity` change from producing a spurious `review_required` transition before `stale`.

### Registration boundaries

- Markdown dependencies are whole-file only. No Markdown-section addressing exists in v0.1.
- Partial-document dependencies use a structured field/object ref. Its JSON-compatible value may come from canonical structured data or from a project producer that reads tracked canonical Markdown and exposes an explicitly bounded derived slice; the original prose can remain Markdown. See the runnable [Markdown field project](../examples/markdown_field_project/README.md).
- Current target/source availability is checked at runtime, not while importing the project extension. This preserves diagnostics when a reviewed file is later deleted or temporarily broken.
- An exact whole target may not simultaneously be a deterministic builder target and a semantic-rule target in v0.1. Current dependency state selects one active receipt per exact target. Field-level semantic refs remain distinct refs and are not affected by this exact-target restriction.
- Exact semantic-rule cycles are rejected.

## Review packet

For a registered semantic target:

```bash
docengine explain TARGET --json
```

returns a `SemanticReviewPacket` containing:

- target identity, current content/value and current revision;
- semantic rule identity and rule revision;
- prior validated receipt, if any;
- prior baseline slice for every previously validated dependency;
- current dependency slice and current version;
- typed comparator diff;
- dependency/rule/target change reasons;
- prior event history;
- deterministic `review_context_id`;
- `semantic_judgment: null`.

The packet is evidence for the reviewer. It does not contain an engine-generated semantic verdict.

A registered rule with no validated receipt is surfaced by `check` using the rule's canonical dependency-type state: `semantic_review`/`compatibility` → `review_required`, `validity` → `stale`. P4 does **not** fabricate a validated receipt/baseline merely to create state.

## Review context token

`review_context_id` fingerprints:

- target ref and current target revision;
- current semantic rule id/revision;
- active prior receipt id, if any;
- the latest state-transition occurrence for this target;
- exact current semantic dependency refs/comparators/versions.

`validate` requires this token. If target, dependency state or rule revision changes after the review packet was obtained, validation fails and the reviewer must obtain a new packet.

The occurrence component is intentional: content-stable receipts may reappear in A → B → A cycles. A later review of identical content is still a **new review occurrence**, not an exact retry of the old decision. Exact retry deduplication applies only while the consumed semantic-validation event is still the active event/state occurrence for that target.

This is the v0.1 protection against knowingly validating stale review evidence. P7 still owns stronger concurrent locking/multi-file transaction recovery.

## Validation command

```bash
docengine validate TARGET \
  --result still-valid|updated \
  --reason "why this is valid" \
  --review-context reviewctx-... \
  [--actor-kind human|ai|ci|unknown] \
  [--actor-label TEXT] \
  [--evidence TEXT ...] \
  [--json]
```

There is no ordinary `force-valid` path in v0.1.

With `--json`, semantic validation input errors—including invalid actor kinds and malformed target refs—remain inside the versioned machine-readable error envelope rather than escaping through argparse or an uncaught reference parser exception.

### `still-valid`

- advances semantic dependency baselines/receipt to the reviewed current dependency state;
- preserves target content;
- rejects the decision if the target content/revision changed since the prior validated target.

### `updated`

- requires a previously validated target;
- requires the current target revision to differ from the previous validated target revision;
- records the edited current target revision as the new validated revision.

Initial validation uses `still-valid`: it means the current target has been reviewed and accepted as-is.

## Actor and evidence metadata

Every semantic validation event stores:

- `decision`;
- non-empty `reason`;
- `actor_kind = human|ai|ci|unknown`;
- optional non-sensitive `actor_label`;
- optional evidence strings;
- `review_context_id`;
- semantic rule id/revision;
- prior receipt id, when one existed.

No personal identity is required.

## Persistence and history

Successful validation:

1. captures new content-addressed baselines for current semantic dependency slices;
2. creates/reuses a content-stable dependency receipt with target revision and semantic rule identity;
3. makes that receipt active with `status=valid`;
4. appends a `semantic_validation` event carrying the explicit review decision metadata.

Old receipts, baselines and events remain inspectable.

A content-stable receipt may be reused, while each real state transition gets its own monotonic `state_revision` event occurrence. Exact retry of the same consumed review context/decision is idempotent and appends nothing; conflicting reuse of the same review context is rejected.

## Integrity

P4 extends persisted integrity checks so that:

```text
valid semantic state
  -> semantic receipt
  -> matching semantic_validation event
  -> matching rule id/revision
  -> current/prior receipt links
  -> content-addressed dependency baselines
```

A semantic validation event may legitimately describe a dependency removed by a changed rule. In that case integrity resolves the reviewed changes against the union of the prior and new receipt dependency sets.

Directly editing `dependency_state.json` is not an official acceptance path. State/event mismatch is detectable by integrity checks, while the supported mutation path is `validate`.

## P4 vs later phases

P4 does not:

- rebuild deterministic targets (`rebuild` later orchestration);
- render/materialize Markdown (P5);
- run sync orchestration (P5);
- provide final release verification (`verify`, P6/P8);
- provide process isolation or multi-file transactional locking (P7).
