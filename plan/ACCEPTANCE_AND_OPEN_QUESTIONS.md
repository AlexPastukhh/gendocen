# Acceptance and Open Questions

## Purpose

Canonical questions/answers/decisions live in `plan/phase_records/P<n>_EXECUTION_RECORD.json`; human view is `plan/QUESTIONS_AND_DECISIONS.md`. The repository-root `OPEN_QUESTIONS_AND_AMBIGUITIES.md` is the discoverable consolidated index for unresolved/deferred policy points and non-blocking questions.

## Adopted architecture

- Markdown-first; structured JSON only where justified.
- Structured/descriptor JSON and dependency runtime state are documentation-owned.
- Materialized file paths live in documentation JSON descriptors; builder/dependency semantics live in code.
- Raw objects are not mutated with derived fields.
- Baselines capture only dependency slices actually referenced.
- Whole-file Markdown dependencies require no JSON conversion.
- Runtime state is changed through engine commands, not manual flag editing.
- Semantic stale/review_required means validity is unconfirmed, not that content is false.
- Acceptance is broader than tests and uses DAX01–DAX20.

## Current implementation state

P0–P2 are accepted. P3 is next.

## Unresolved questions

None before P3 implementation. Emergent questions discovered during implementation must be added to the relevant phase record.

## Newly resolved user decisions

- `P4/Q4.3`: v0.1 has no Markdown section-level dependency addressing. Whole-file dependencies are allowed for plain Markdown; if dependency granularity must target only part of a document, that content is moved to structured JSON.
- `P8/Q8.1`: `docengine verify` always emits a complete verification report. Blocking findings, including unresolved required `review_required`, produce `ok=false` and a non-zero exit code; this is not an execution crash.
