# P3 Acceptance Review — Dependency receipts, baselines, comparators, diff and state

Date: 2026-10-02
Decision: **ACCEPTED**
Runtime build: **0.1.0.dev7**
Next phase: **P4 — Semantic review and validation workflow**

## Implemented

- documentation-owned dependency runtime under `docs/_dependency/...`;
- content-addressed baseline slices;
- deterministic dependency receipts with full receipt hash;
- current dependency state and append-only events;
- exact field/resource/plain-Markdown dependency persistence;
- built-in deterministic comparators: `exact`, `json_structured`, `sequence`, `set`, `text_unified`;
- structural diff and state classification (`valid`, `stale`, `review_required`, `build_required`, `invalid`);
- package-wide builder/helper revision invalidation;
- reverse dependency graph;
- `status`, `check`, `diff`, `explain`, `history`, `graph` runtime/CLI surfaces;
- read-only diagnostics that remain available even if current project builder code cannot import;
- integrity checks across state, receipts, baselines and events;
- explicit semantic-review receipts that pin the exact target revision reviewed.

P3 intentionally does **not** make semantic truth judgments, advance semantic validation baselines after human/AI review, render/rebuild Markdown, or provide final `verify`; those are P4–P8 responsibilities.

## Acceptance criteria

| Criterion | Result | Primary evidence |
|---|---|---|
| P3-A1 exact field slices; unrelated fields do not invalidate | PASS | `tests/test_p3_dependencies.py`, `plan/evidence/P3/field_dependency_and_diff.json` |
| P3-A2 whole-file Markdown dependency without JSON twin | PASS | Markdown dependency tests + `plan/evidence/P3/markdown_dependency_review.json` |
| P3-A3 comparator diff is baseline-vs-current and retry-stable | PASS | comparator/diff tests |
| P3-A4 structural change updates runtime state without semantic verdict/content mutation | PASS | Markdown semantic-review tests |
| P3-A5 reverse graph identifies exactly affected targets | PASS | reverse-graph test |
| P3-A6 receipt/state/events remain mutually explainable; corrupt fixtures detected | PASS | integrity tests + `plan/evidence/P3/integrity_detection.json` |
| P3-A7 builder/helper revision change causes `build_required` | PASS | builder-revision test + evidence JSON |
| P3-A8 dependency persistence is docs-owned; read-only queries do not create state; path escapes rejected | PASS | read-only/path/symlink tests |
| P3-A9 human/JSON surfaces expose evidence without semantic verdict and remain domain-neutral | PASS | CLI tests + sample/product-tax fixtures |
| P3-A10 persisted formats are versioned/cross-linked/schema/documentation/package consistent | PASS | schemas, spec audit, package audit; final wheel/archive gate pending |

## Real defects found and corrected during P3 acceptance review

1. Read-only dependency query paths could have created runtime directories if stores eagerly initialized; stores now create parents only on writes.
2. Exact retry of the same build needed idempotent baseline/receipt/event behavior; deterministic logical IDs now avoid divergent history.
3. Incompletely tracked P2 provenance could have been mislabeled valid; it is now `invalid` with `audit_incomplete`.
4. Missing dependency source/current builder must be `invalid` with explicit diagnostics, not disguised as an ordinary semantic/build change.
5. Persisted diagnostics originally depended too strongly on current builder imports; `status/history/graph` now read persisted state independently.
6. Integrity originally checked only part of the state→receipt→baseline/event chain; target/receipt links and canonical refs were strengthened.
7. Explicit semantic receipts stored `target_revision` but did not compare it. Editing the reviewed target could therefore leave old validation apparently current. P3 now pins and checks target revision.
8. State/event `changed_dependencies` could claim sources absent from their receipt while integrity still returned `ok=true`. Cross-link membership and active-receipt state identity are now checked.
9. Persisted receipt parsing could coerce malformed `audit_complete` values through Python truthiness. Audit-critical primitive types are now validated strictly.
10. Human Q&A documentation lagged canonical P3 phase records; `QUESTIONS_AND_DECISIONS.md` has been regenerated from the phase records.

These are closed with regression evidence. They are not listed as remaining limitations.

## Deliberate boundaries, not defects

- Project Python remains cooperative/trusted rather than sandboxed.
- Builder revision is package-wide and may over-invalidate.
- v0.1 has no virtual collection-ref syntax; aggregate builders store multiple exact refs.
- Markdown section-level dependency addressing remains out of v0.1; narrower stable semantics use structured JSON.
- Crash-safe multi-file transaction/locking is P7 hardening; P3 uses confined atomic JSON replacement plus append-only event writes.

## Questions

All P3 pre-execution and emergent questions are answered. No unresolved user-owned or blocking question remains before P4.


## Post-acceptance independent axis finding

A later axis/regression review reproduced a real revert-cycle defect: a target could validate against receipt A, then B, then the exact same content-stable receipt A again. Receipt timestamps made B look "latest" to graph/integrity helpers, while deterministic event deduplication suppressed the later A re-activation from append-only history.

Correction: receipts remain content-stable; persisted state is authoritative for the active receipt; each real state mutation advances `state_revision`; event identity includes that revision. Regression coverage proves A→B→A keeps three event occurrences, current state/graph point to A, and integrity remains green.
