# P3 Post-Acceptance Independent Axis Review

Date: 2026-10-02

Decision: **P3 remains accepted after correction of one reproduced post-acceptance defect.** No unresolved user-owned or blocking question remains before P4.

Runtime build after this correction: **0.1.0.dev7**.

This review intentionally distinguishes confirmed defects from ambiguous/deferred design points. It does not downgrade a phase merely because another implementation is imaginable.

## Confirmed finding discovered by this review

### PA3-F001 — content-stable receipt re-activation lost occurrence ordering

Reproduced sequence:

```text
validate target against receipt A
validate same target against receipt B
validate same target against the exact same content as receipt A
```

The third validation correctly reused content-stable receipt A, but the old implementation used receipt `validated_at` to infer the "latest" receipt and content-stable event IDs to deduplicate events. This caused two correctness failures:

- graph/integrity helpers could treat B as current even though persisted state selected A;
- the later A re-activation could disappear from append-only event history.

### Correction

The implementation now separates **evidence identity** from **transition occurrence identity**:

- `receipt_id` stays content-stable;
- persisted dependency state is authoritative for the currently active receipt;
- every actual state mutation advances project-level `state_revision`;
- new event IDs include `state_revision`;
- exact retry when state did not change emits no duplicate event;
- A → B → A produces state revisions 1 → 2 → 3 and three history occurrences;
- graph uses active receipts selected by state, not receipt timestamps.

Evidence:

- `src/docengine/dependencies.py`
- `tests/test_p3_dependencies.py::P3ReceiptReactivationTests::test_reactivating_content_stable_receipt_is_current_and_has_new_event_revision`
- `plan/evidence/P3/receipt_reactivation.json`

## P3 mapped DAX axes after correction

| Axis | Result | Independent-review conclusion |
|---|---|---|
| DAX01 Markdown-first boundary | PASS | Plain Markdown remains a first-class whole-file dependency without forced JSON. |
| DAX02 Documentation ownership/layout | PASS | Dependency evidence/state remains under configured documentation-owned `_dependency`. |
| DAX03 Resource/schema/version integrity | PASS | Strict persisted parsing remains intact; additive `state_revision` is schema-declared and legacy P3 state/events without it remain readable. |
| DAX04 Path confinement/data safety | PASS | No new write path escapes dependency-root confinement; prior symlink/path protections remain covered. |
| DAX05 Raw/derived separation/provenance | PASS | Receipt/state changes do not mutate raw or derived source objects. |
| DAX06 Dependency capture/granularity | PASS | Exact field/resource/whole-file refs remain unchanged; collection identity remains an explicit deferred design choice rather than an invented ref type. |
| DAX07 Baseline/comparator/diff correctness | PASS | Baseline and typed diff behavior remains correct; re-activation regression now proves current selection is not inferred from stale receipt timestamps. |
| DAX08 Invalidation/state semantics | PASS | State is authoritative for active receipt and structural changes retain build/review/stale/invalid semantics without semantic claims. |
| DAX09 Semantic review/agency | PASS for P3 boundary | P3 still exposes evidence only; semantic acceptance remains P4/human/AI authority. |
| DAX10 Determinism/idempotency | PASS | Content-stable receipt retry-idempotency is preserved while monotonic state revisions retain repeated transition history. |
| DAX12 CLI boundaries | PASS | Read-only vs `check` mutation boundary remains unchanged. |
| DAX13 AI/CI usability | PASS for P3 boundary | Machine-readable persisted diagnostics remain available and explain active receipt/history correctly. |
| DAX14 History/provenance/diagnostics | PASS | State→active receipt, event→receipt/state revision, receipt→baseline and changed-dependency membership are integrity-checkable. |
| DAX17 Domain independence | PASS | Generic dependency runtime remains domain-neutral. |
| DAX19 Test assurance | PASS | Added a reproduced A→B→A regression test plus legacy state-revision compatibility coverage. |
| DAX20 Release/handoff integrity | PASS after package regeneration | Docs, question view, schemas, wheel, manifest and handoff package are regenerated from the corrected state before final handoff. |

## Adjacent axes deliberately not claimed as globally closed

- **DAX15 crash/concurrency/transactionality:** still intentionally deferred to P7. P3 has confined/atomic individual-file writes but does not claim multi-file transactional recovery or locking.
- **DAX16 migration/backward compatibility:** global migration machinery remains P7. This review did verify a concrete compatibility slice: legacy P3 state/events without `state_revision` are still readable, and the next changed state upgrades to revisioned writes.
- **DAX18 performance/scalability:** remains P7 hardening scope.

## Ambiguities / non-blocking policy points

No newly unresolved policy question was created by this audit. The existing aggregate/collection-ref choice remains recorded in root `OPEN_QUESTIONS_AND_AMBIGUITIES.md` as an accepted v0.1 default. The receipt re-activation issue was a confirmed defect, so it is recorded as resolved emergent decision Q3.E10 rather than softened into an ambiguity.
