# P4 Acceptance Review — Semantic review and validation workflow

Date: 2026-10-02
Decision: **ACCEPTED**
Runtime build: **0.1.0.dev9**
Next phase: **P5 — Renderers, materialization, drift detection and sync**

## Implemented

- project-code semantic dependency registry with stable rule identity/revision;
- review packets containing target/current revision, prior receipt, old/current dependency slices, typed diffs and history;
- explicit `review_context_id` binding the reviewed target/dependency/rule state;
- official `validate TARGET --result still-valid|updated --reason ... --review-context ...` workflow;
- actor metadata (`human|ai|ci|unknown`), optional non-sensitive label and evidence list;
- `still-valid` baseline advancement without target mutation;
- `updated` validation only after an already validated target has actually changed;
- stale review-context rejection without state advancement;
- exact retry idempotency and conflicting reuse detection;
- semantic rule revision invalidation;
- initial registered rule surfaced as `review_required` without creating fake validated state;
- semantic review history linked to receipts/state revisions;
- direct/manual state acceptance detected as integrity failure;
- runtime diagnostics remain usable when current semantic target/source becomes unavailable;
- exact whole-target deterministic-builder/semantic-rule ownership overlap rejected in v0.1 single-active-receipt state.

P4 does **not** ask an LLM to decide semantics automatically. `explain` returns evidence with `semantic_judgment=null`; the explicit human/AI caller supplies the verdict through `validate`.

## Acceptance criteria

| Criterion | Result | Primary evidence |
|---|---|---|
| P4-A1 upstream semantic change → `review_required` without semantic claim | PASS | `still_valid_flow.json`, semantic tests |
| P4-A2 review packet contains old/current slices, diff, target and prior context | PASS | `initial_review_packet.json`, `updated_flow.json`, `REVIEW_PACKET.schema.json` |
| P4-A3 `still-valid` advances baseline without target edit; `updated` requires changed target | PASS | `still_valid_flow.json`, `updated_flow.json`, validation tests |
| P4-A4 direct state edit is not an acceptance path; official validate records history | PASS | `manual_state_edit_integrity.json`, `initial_history.json` |
| P4-A5 old validation receipts/events remain inspectable | PASS | `still_valid_flow.json`, `updated_flow.json`, history tests |
| P4-A6 exact retry is idempotent and conflicting reuse is rejected | PASS | `idempotent_retry.json`, retry tests |
| P4-A7 code-owned/versioned rules are inspectable; exact builder/semantic target overlap rejected | PASS | registry/graph tests, `semantic_rules.py` |
| P4-A8 stale context rejected and P3 evidence remains backward-readable | PASS | `stale_context_rejection.json`, P3 regression suite |
| P4-A9 CLI JSON errors + actor/reason/evidence + package/handoff consistency | PASS | CLI tests + dev9 post-axis clean-install/package evidence |

## Confirmed defects found and corrected during P4 implementation/review

1. Semantic extension loading initially required target/source availability, which hid P3 diagnostics when a document was deleted. Availability is now checked at runtime, not import registration.
2. A registered semantic rule with no baseline needed to appear as initial `review_required` without fabricating a receipt/state entry.
3. Semantic validation needed a consumed-context token; otherwise target/dependency/rule state could change between `explain` and `validate`.
4. `updated` needed a strict prior-target/change requirement; otherwise it could be used as an alternate spelling of initial/still-valid validation.
5. CLI invalid/missing `validate` inputs originally risked argparse exits rather than the versioned machine-readable JSON envelope.
6. Exact builder target and semantic-rule target ownership would compete for one active receipt in the current P3 state model. Exact overlap is rejected until a multi-mode state model exists.
7. Review integrity needed the union of prior/current receipt sources when a rule revision removes an old dependency.
8. P4 persisted additions needed to remain additive/backward-readable without pretending a migration was required; optional fields stay inside persisted schema `1.0.0`.

These are corrected and regression-tested; they are not remaining defects.

## Deliberate boundaries / ambiguities

No new unresolved user-owned ambiguity was created by P4. Existing top-level A1–A5 remain in `OPEN_QUESTIONS_AND_AMBIGUITIES.md`.

The exact builder/semantic target overlap restriction is an accepted v0.1 implementation default, not a hidden limitation: current state has one active receipt per exact target. A future multi-mode/multi-receipt state design may relax it if a real use case requires simultaneous computational and semantic ownership of the same exact target.

## Questions

All P4 pre-execution and emergent questions are answered. No unresolved blocking or user-owned question remains before P5.

## Post-acceptance independent audit addendum — dev9

A later independent axis review reproduced and corrected five additional P4-scope defects before P5 handoff:

1. recurrent A → B → A → B semantic contexts could reuse an old consumed review and report duplicate success without re-validating current state;
2. initial/legacy `validity` rules could be reported `review_required` instead of canonical `stale`;
3. semantic rule-type changes could first persist status using the previous receipt type;
4. invalid `--actor-kind` could terminate in argparse instead of JSON protocol;
5. malformed target refs could escape semantic/dependency CLI boundaries as traceback/exit 1.

The dev9 corrections are covered by `tests/test_p4_semantic.py` and `plan/evidence/P4/post_axis_audit/`. P4 remains accepted after the final package gate. One mixed semantic↔builder cycle question is deliberately recorded as non-blocking P5/Q5.E1 rather than misclassified as a P4 defect.
