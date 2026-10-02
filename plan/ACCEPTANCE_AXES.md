# Acceptance Axes

Статусы: `pass`, `partial`, `fail`, `not_tested`, `not_applicable`.

**Правило приёмки шага:** criteria pass, blocking questions resolved, а mapped axes проходят для того risk slice, который данный phase вводит или реально упражняет. `PASS` в phase record не означает, что ось закрыта глобально. **Правило финального release P8:** consolidated review заново покрывает каждую global release-gate axis по системе целиком, включая DAX15, завершённую до release.

## DAX01 — Purpose & Markdown-first boundary
Engine preserves Markdown-first documentation and only introduces structured/managed machinery where explicitly justified.
Release gate: **yes**.

## DAX02 — Documentation ownership & storage layout
Structured data and dependency state remain documentation-owned, with mirrored _structured layout and clear separation from engine code.
Release gate: **yes**.

## DAX03 — Resource identity, schema & version integrity
Resources, schemas, refs, versions and metadata envelopes are unambiguous, validated and evolvable.
Release gate: **yes**.

## DAX04 — Path confinement & data safety
Reads/writes/materialization cannot escape configured roots or silently destroy canonical data.
Release gate: **yes**.

## DAX05 — Raw/derived separation & provenance
Raw objects remain immutable; derived objects are new values with traceable provenance.
Release gate: **yes**.

## DAX06 — Dependency capture & granularity correctness
Tracked reads and explicit rules capture the exact field/object/file/collection dependencies intended by code.
Release gate: **yes**.

## DAX07 — Baseline, comparator & diff correctness
Only relevant dependency slices are baselined; comparisons and diffs are semantically correct and reproducible.
Release gate: **yes**.

## DAX08 — Invalidation & state semantics
Upstream changes deterministically produce correct stale/review/build-required states without claiming semantic falsity.
Release gate: **yes**.

## DAX09 — Semantic review & human/AI agency
The engine exposes evidence and accepts explicit review decisions; it never invents semantic verdicts.
Release gate: **yes**.

## DAX10 — Builder/validator determinism & idempotency
Deterministic operations are reproducible, retry-safe and do not create divergent state on repeated execution.
Release gate: **yes**.

## DAX11 — Materialization & derived-view parity
Generated views are reproducible from canonical inputs; drift is detectable; output ownership is explicit.
Release gate: **yes**.

## DAX12 — CLI contract, exit codes & command boundaries
Commands have stable responsibilities, predictable mutations, documented exit codes and consistent human/JSON surfaces.
Release gate: **yes**.

## DAX13 — AI/CI usability & machine-readable protocol
A new AI/CI consumer can inspect, act, validate and verify without editing internal runtime files directly.
Release gate: **yes**.

## DAX14 — History, provenance, diagnostics & repairability
Receipts/events/reasons make changes explainable and allow diagnosis/reconciliation after failures.
Release gate: **no**.

## DAX15 — Crash, retry, concurrency & transactional integrity
Interrupted or concurrent operations do not leave contradictory canonical/runtime state.
Release gate: **yes**.

## DAX16 — Migration & backward compatibility
Persisted state and project contracts are versioned and can evolve without silently invalidating prior evidence.
Release gate: **no**.

## DAX17 — Domain independence, configurability & extensibility
Core runtime contains no research-domain assumptions and project-specific code plugs in through explicit interfaces.
Release gate: **yes**.

## DAX18 — Performance & scalability
Graph traversal, diffing and materialization remain practical on declared synthetic project sizes.
Release gate: **no**.

## DAX19 — Test quality & assurance
Unit, integration, property/fixture and end-to-end tests exercise semantics rather than only happy-path compilation.
Release gate: **yes**.

## DAX20 — Release, manifest, documentation & handoff integrity
Package contents, docs, schemas, examples, manifests and handoff instructions agree with implemented behavior.
Release gate: **yes**.
