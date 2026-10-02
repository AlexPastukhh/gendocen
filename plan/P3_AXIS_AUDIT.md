# P3 DAX Audit

Date: 2026-10-02
Decision: **PASS for the P3 risk slice**. Global axis closure remains P8.

| Axis | P3 result | Evidence / boundary |
|---|---|---|
| DAX01 Markdown-first boundary | PASS | Whole-file Markdown can participate directly in dependency review; no JSON twin or section parser is forced. |
| DAX02 Documentation ownership/layout | PASS | Receipts/baselines/state/events live under configured `docs/_dependency`; engine/project code remains outside documentation state. |
| DAX03 Identity/schema/version integrity | PASS | Canonical refs, state schema version, receipt/content hashes, strict persisted parsing and builder revision evidence. |
| DAX04 Path confinement/data safety | PASS | Runtime writes are confined below dependency root and reject symlink/path escapes; read-only queries create no state. |
| DAX05 Raw/derived separation/provenance | PASS | P2 provenance is persisted without mutating raw inputs; incomplete audit never becomes valid; code revision remains explicit derivation input. |
| DAX06 Dependency capture/granularity | PASS | Exact field/resource/plain-file slices; aggregate semantics use many exact edges rather than invented collection refs. |
| DAX07 Baseline/comparator/diff correctness | PASS | Content-addressed relevant slices and deterministic built-in comparator behavior; field-unrelated edits do not invalidate. |
| DAX08 Invalidation/state semantics | PASS | Dependency/code/target structural changes map deterministically to build/review/stale/invalid without claiming semantic falsity. |
| DAX09 Semantic review & agency | PASS for P3 boundary | P3 exposes structural evidence only. Human/AI semantic acceptance is intentionally deferred to P4. |
| DAX10 Determinism/idempotency | PASS | Content-addressed baselines and receipts plus monotonic `state_revision` event occurrences preserve retry idempotency without losing later re-activation of an older receipt. |
| DAX12 CLI boundaries | PASS | `status/diff/explain/history/graph` are read-only; `check` may update only dependency state/events. |
| DAX13 AI/CI usability | PASS for P3 boundary | All P3 CLI surfaces provide versioned JSON; diagnostics remain readable even with broken current builder code. |
| DAX14 History/provenance/diagnostics | PASS | Receipt↔baseline, state↔active receipt, event↔receipt/state-revision and changed-dependency membership are integrity-checked. |
| DAX17 Domain independence | PASS | Same runtime handles plain Markdown and unrelated product/tax structured project. |
| DAX19 Test assurance | PASS | Positive, negative, mutation, corruption, retry, path, builder-revision, target-revision and CLI scenarios. |
| DAX20 Release/handoff integrity | PASS | Docs/schemas/examples/phase records are synchronized; final wheel/manifest/archive checks remain the last package gate. |

## Important semantic distinction

`review_required`/`stale` means prior validity is no longer confirmed against current dependency/target state. It is **not** a semantic verdict that the document is false.

## P3-specific integrity closure

The final P3 integrity model checks that:

```text
state target → currently active receipt for the same target
receipt dependency → content-addressed baseline
state/event changed dependency → dependency source recorded by receipt
builder change → builder pseudo-edge recorded in diff/state
history event → existing receipt for the same target
explicit review → exact target revision reviewed
```

Malformed audit-critical receipt/event field types are corruption and are not coerced.
