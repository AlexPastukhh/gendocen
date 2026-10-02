# P4 Post-Acceptance Independent Axis Review — dev9 final

Date: 2026-10-02

Decision: **P4 remains accepted after corrections.** Independent post-acceptance review reproduced five real defects, corrected them, and reran the complete P0–P4 functional surface. No unresolved user-owned or blocking question remains before P5.

Runtime build: **0.1.0.dev9**.

This review does not classify an alternative implementation as a defect unless executable behavior contradicts an accepted contract/axis.

## Confirmed defects reproduced and corrected

1. **Semantic review occurrence identity reused old consumed contexts.** In an A → B → A → B cycle, receipt/dependency content could recur exactly, recreating the same `review_context_id`. `validate` then returned `duplicate=true` from an old event while the target remained `review_required`. Review context now includes target state-transition occurrence identity, and duplicate success is allowed only while that consumed event is still the active event/state occurrence for the target.
2. **Initial/legacy `validity` rules were hardcoded to `review_required`.** `explain` correctly computed `stale`, while `check` returned `review_required`. Initial and legacy-metadata semantic classification now follows the rule dependency type: semantic/compatibility → `review_required`, validity → `stale`.
3. **Rule-type changes were classified by the old receipt type first.** `semantic_review → validity` could persist a spurious `review_required` transition before the current rule correctly implied `stale`. Semantic targets are now checked once with the current rule dependency type.
4. **Invalid `--actor-kind` escaped JSON through argparse.** It now reaches semantic runtime validation and returns the normal versioned JSON error envelope.
5. **Malformed TARGET refs escaped CLI error handling.** `validate`/`explain` (and the shared dependency command boundary) now catch `RefError` and return exit 2 with the machine-readable error envelope instead of traceback/exit 1.

Regression evidence:

- `tests/test_p4_semantic.py`
- `plan/evidence/P4/post_axis_audit/semantic_recurrence.json`
- `plan/evidence/P4/post_axis_audit/initial_validity_status.json`
- `plan/evidence/P4/post_axis_audit/rule_type_transition.json`
- `plan/evidence/P4/post_axis_audit/cli_error_envelopes.json`

## Mapped DAX conclusions after correction

| Axis | Result | Independent conclusion |
|---|---|---|
| DAX01 | PASS | Markdown-first boundary remains intact; no Markdown-section addressing or JSON twin requirement was introduced. |
| DAX02 | PASS | Semantic rules remain project-code-owned; receipts/baselines/state/events remain documentation-owned. |
| DAX03 | PASS | Rule/receipt/context identities are explicit; recurrent semantic contexts now distinguish transition occurrence from content identity. |
| DAX04 | PASS | P4 adds no unconfined storage/write root and continues using confined P3 stores. |
| DAX05 | PASS | Validation changes evidence/state, never raw/derived object identity implicitly. |
| DAX06 | PASS for P4 exact-ref model | Semantic rules use canonical exact refs/comparators; exact builder/semantic target overlap remains rejected. Mixed cross-mode cycles are listed separately as a P5 ambiguity, not silently declared impossible. |
| DAX07 | PASS | Review evidence compares validated baseline slices with current slices and advances baselines only after explicit validation. |
| DAX08 | PASS | Current rule type controls semantic invalidation state consistently, including initial/legacy/type-transition paths; no semantic falsity is inferred. |
| DAX09 | PASS | Engine supplies evidence with `semantic_judgment=null`; human/AI/explicit caller supplies still-valid/updated plus reason. |
| DAX10 | PASS | Exact retry stays idempotent while recurrent A/B state occurrences create new review contexts/events. |
| DAX12 | PASS | `explain` is read-only, `validate` is explicit mutation, and malformed semantic CLI values/refs remain in the versioned error protocol. |
| DAX13 | PASS | JSON review/validation/error surfaces are usable by AI/CI without direct internal-state edits. |
| DAX14 | PASS | Recurrent state transitions remain visible in append-only history; rule-type changes do not create spurious old-type events. |
| DAX16 | PASS for additive P4 slice | Current runtime still reads legacy P3 evidence; full bidirectional migration/version policy remains P7. |
| DAX17 | PASS | Core semantic runtime remains domain-neutral; sample meaning stays in project code. |
| DAX19 | PASS | Coverage now includes semantic recurrence, all supported semantic dependency-type state mappings, rule-type transitions, malformed actor/ref CLI inputs, plus full prior-phase regression. |
| DAX20 | PASS | Final dev9 wheel, manifest, clean-installed workflow, manifest-only portable probe and exact-file-set archive gate pass; global release closure remains P8. |

## Deliberate boundaries / not classified as P4 defects

- **Cooperative Python tracking/isolation** remains A1 and belongs to hardening policy.
- **Package-wide builder revision** may over-invalidate but is correctness-conservative.
- **Single active receipt per exact target** still prohibits exact builder/semantic ownership overlap by design.
- **Crash-atomic multi-file validation writes/locking** remain P7; P4 rejects known stale context but does not claim transactional concurrency recovery.
- **Persisted schema 1.0.0 additive fields** prove new-runtime backward reading of P3 evidence; the complete migration framework remains P7.

## New ambiguity / non-blocking question for P5

A concrete mixed graph was reproduced and accepted by current P4:

```text
semantic target A -> derived field B
builder target B   -> reads A
```

Pure builder recursion and pure semantic-rule cycles are already rejected independently, but this mixed cycle is not globally classified today. It is **not declared a P4 defect** because a semantic edge stops automatic acceptance and can intentionally break an operational loop. However P5 `sync` needs explicit SCC/termination semantics.

Recorded as **P5/Q5.E1 (non-blocking, pending)** with evidence `plan/evidence/P4/post_axis_audit/mixed_cycle_ambiguity.json`.
