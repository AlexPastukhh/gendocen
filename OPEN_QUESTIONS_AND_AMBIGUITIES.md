# Open Questions, Ambiguities and Deferred Policy Choices

This is the **discoverable top-level index** for design points that are deliberately not classified as current defects, plus non-blocking questions from phase planning.

Read this file after `START_HERE_AGENT.md` and before implementing the next phase.

Canonical question/answer/decision records remain in `plan/phase_records/P<n>_EXECUTION_RECORD.json`. This file is an index and handoff aid; when a point becomes a firm decision, the relevant phase record must also be updated.

Additive post-P8 field work has its canonical current plan/decisions in `plan/FIELD_DEPENDENCY_EXPANSION.md` (`FIELD-EXPANSION-1`). Its implementation is delivered in runtime `0.1.0.dev23`; local acceptance evidence is recorded there separately from historical accepted phase records.

## Status vocabulary

- **OPEN / DEFERRED** — a legitimate future design choice; not required for the next phase unless promoted by evidence.
- **ACCEPTED DEFAULT** — a deliberate v0.1 choice; not a defect, but may later be optimized.
- **RESOLVED** — question was non-blocking but already has an answer/decision.
- **WATCH ITEM** — not a question yet; implementation must preserve an existing invariant and create an emergent question only if evidence forces a choice.


## Mandatory recording rule for future implementation and audits

Whenever implementation, acceptance review, or an independent axis audit encounters a point that is genuinely neither a confirmed defect nor an obviously normal/settled behavior, it **must be added to this file before the phase/package is handed off**.

Each new entry must state:

- what is ambiguous or policy-sensitive;
- whether it is `OPEN / DEFERRED`, `ACCEPTED DEFAULT`, `RESOLVED`, or a `WATCH ITEM`;
- why it is **not** currently classified as a defect;
- what evidence or future condition would promote it into a defect, requirement, or blocking question;
- the canonical phase/question/decision reference when one exists.

Confirmed defects belong in the relevant phase audit/execution record and must not be softened into this ambiguity list. Clearly normal behavior does not need an entry. New user-owned questions must also be copied into the relevant canonical phase execution record; this top-level file remains the discoverable index, not the canonical owner of answers.

## Current blocking questions

**None.** Final P8 release has no unresolved user-owned or implementer-owned blocking question.

## Ambiguous / policy-sensitive points carried from P2

### A1 — Cooperative builder tracking vs stronger isolation

**Status:** OPEN / DEFERRED, non-blocking.

Project builder code is trusted/cooperative Python. `BuildContext` records dependency-aware reads, and provenance exposes `tracking_assurance="cooperative"`, but the runtime does not sandbox arbitrary direct filesystem/network access by builder code.

This is not currently classified as a defect because the trust model is explicit. A future hardening decision may choose stronger isolation or restricted execution if real usage shows that cooperative tracking is insufficient.

**Potential future question:** Should hardened releases isolate project builder code strongly enough to enforce dependency completeness rather than merely record cooperative usage?

**Earliest likely phase:** P7 hardening, unless evidence appears earlier.

### A2 — Project-specific schemas for derived `data`

**Status:** OPEN / DEFERRED, non-blocking.

P2 validates the generic `DerivedObject` envelope and JSON compatibility of built output. It does not require a project-specific JSON Schema for every derived object's `data`.

This is not a current defect because no accepted P2 contract requires per-derived-type schemas. A later phase may add optional or required output schemas if concrete validation/materialization needs justify them.

**Potential future question:** Should project-derived outputs support optional schemas, required schemas, or remain builder-validated only?

### A3 — Builder revision granularity

**Status:** ACCEPTED DEFAULT for v0.1; optimization deferred.

`builder_revision` hashes the project Python package conservatively. Therefore an unrelated Python edit in the package may mark more deterministic targets `build_required` than strictly necessary.

This favors correctness over minimal rebuilds. P3 must persist and compare this package-wide revision. Finer per-builder/helper code provenance is a future optimization only if rebuild noise becomes material.

### A4 — `ctx.get()` object-wrapper metadata

**Status:** ACCEPTED CONTRACT LIMITATION; non-blocking.

`ctx.get()` returns an object wrapper that includes diagnostic/infrastructure metadata in addition to canonical domain data. The semantic dependency is the canonical domain value; source paths and provenance metadata must not be used as hidden derivation inputs.

This boundary is currently enforced by the cooperative programming contract rather than a restricted value-only wrapper.

**Potential future question:** If misuse appears in real projects, should `ctx.get()` return a restricted semantic-value view and expose diagnostics through a separate API?


### A5 — Aggregate dependencies without a virtual collection ref

**Status:** ACCEPTED DEFAULT for v0.1; dedicated collection identity deferred.

P3 deliberately does **not** invent `collection://...`, `field_set://...`, or another virtual reference syntax. An aggregate builder records the concrete addressable inputs it actually consumed as multiple exact `resource://...`, field, or `file://...` dependencies.

This is not currently classified as a defect: exact refs preserve explainability and avoid introducing collection membership/version semantics before there is a concrete use case. The tradeoff is that a conceptual collection does not yet have its own stable identity that can invalidate a target when membership changes unless the builder actually discovers/reads the changed member set through addressable inputs.

**Potential future question:** When real projects need dependency on *collection membership itself* rather than a known set of exact members, should the engine introduce a canonical collection resource/ref and explicit membership snapshot semantics?

**Earliest likely phase:** P7 hardening or a later extension, unless P4–P6 expose a concrete blocking use case.

**Canonical related decision:** P3/Q3.E4.

### A6 — Mixed semantic ↔ deterministic dependency cycles

**Status:** RESOLVED IN P5 (Q5.E1).

P2 rejects recursive deterministic builder cycles and P4 rejects exact semantic-rule cycles, but the combined persisted graph can still contain a mixed cycle such as:

```text
semantic A -> derived field B
builder B  -> reads A
```

A concrete fixture confirms that P4 can persist this graph. This is not automatically classified as a P4 correctness defect because the semantic member is never auto-accepted and can intentionally stop automated progression. P5 `sync`, however, must define termination/attention behavior for a mixed strongly-connected component rather than assuming the combined graph is acyclic.

**Decision:** P5 permits mixed SCCs only with explicit bounded sync semantics. Deterministic members run at most once per sync occurrence; semantic members remain unresolved review work; affected mixed SCCs return `attention_required`. Pure deterministic executable cycles remain errors.

**Canonical tracking:** P5/Q5.E1. Evidence: `plan/evidence/P5/mixed_scc.json`.

### A7 — Windows shared-reader lock parity

**Status:** RESOLVED / ACCEPTED v0.1 SUPPORT CONTRACT (P8/Q8.E3).

P7 uses true shared-reader/exclusive-writer `fcntl` locking on POSIX. The Windows `msvcrt` fallback safely serializes access but does not guarantee concurrent-reader parity.

**P8 decision:** safe Windows serialization is accepted for v0.1. Concurrent-reader parity on Windows is not a v0.1 release requirement and is deferred as a post-v0.1 optimization. This is a documented portability limitation, not an unresolved release question or a correctness defect.

### A8 — Independent computed fields across documents

**Status:** RESOLVED / IMPLEMENTED; native API deferred, non-blocking.

The user selected a project helper over immediate native field-target registration. Independent computations are represented by small internal whole resources and final documents compose their values. The runnable example and new-chat instructions are in `docs/FIELD_DEPENDENCIES.md` and `examples/field_dependency_project/README.md`; canonical additive decision: `plan/FIELD_DEPENDENCY_AUTHORING.md` / `FIELD-AUTHORING-1`.

The extension in `plan/FIELD_DEPENDENCY_EXPANSION.md` / `FIELD-EXPANSION-1` implements independent nested fields and composition at every level, explicit raw ownership/overrides, backward-compatible pointer-path APIs and stable-operation reuse. The copyable helper is demonstrated in `examples/nested_field_project`; installed runtime `0.1.0.dev23` supplies BuildOperation and the narrow P-2 transitive-source error fix. Native field-target registration and persistent cross-command reuse remain deferred. Existing P0–P8 historical acceptance records are preserved; platform limits are stated in the expansion evidence.

### A9 — Recursive dependency depth

**Status:** ACCEPTED DEFAULT by user, non-blocking for the implemented field expansion.

Retain recursive execution and the normal Python recursion limit. Independent review observed 128 levels passing and 256 failing in one Python 3.12/Linux environment; these numbers are evidence, not a fixed supported-depth guarantee. No depth requirement was promoted into a current defect. Return if an actual project exceeds the limit; test a bounded limit increase or revisit iterative execution when long chains become routine. Canonical decision: `FIELD-EXPANSION-1` / FE-D06; review follow-up D-3.

### A10 — Dynamic array membership and cross-command field reuse

**Status:** OPEN / DEFERRED, non-blocking.

The expansion permits paths inside existing arrays but does not independently create/resize/reorder their elements; canonical raw data or an atomic array producer owns shape. Operation cache ends with the command and does not persist field values. These are deliberate scope boundaries, not current defects. Revisit stable per-element identity when independently changing array membership is required, or persistent reuse when measurements show material repeated cost across commands. Canonical references: `FIELD-EXPANSION-1` / FE-D05, FE-D09 and section 8.

## Historical non-blocking implementation questions already resolved

These are included for completeness because they are explicitly marked non-blocking in canonical phase records. They are not open decisions.

### P0 / Q0.E1 — Offline clean-environment installation

**Status:** RESOLVED.

Acceptance installs the prebuilt wheel in a clean environment. Source/editable installation is a development workflow and may require build tooling; build tooling is not a runtime dependency.

### P0 / Q0.E2 — Meaning of phase-local DAX PASS

**Status:** RESOLVED.

A DAX `PASS` inside an early phase means that the phase-specific risk slice passed. It does not globally close the axis. P8 performs consolidated global release-gate review.

### P0 / Q0.E3 — Transient test/runtime artifacts and manifest integrity

**Status:** RESOLVED.

`.pytest_cache`, `__pycache__`, bytecode, `.coverage`, and `*.egg-info` are transient and are excluded from canonical manifest file-set comparison. Regression coverage protects the tests→audit workflow.

### P1 / Q1.E6 — `pytest` in source-package test extras

**Status:** RESOLVED.

The optional `test` extra includes `pytest` and `jsonschema`; runtime dependencies remain empty. This makes the documented source-checkout test command reproducible without changing runtime portability.

### P2 / Q2.E12 — Meaning of `audit_complete`

**Status:** RESOLVED.

`audit_complete` is not proof that arbitrary Python performed no hidden I/O. Provenance explicitly says `tracking_assurance=cooperative`; stronger isolation is the deferred A1 policy question above.

## Non-blocking phase questions already recorded

### P3 / Q3.8 — How precise must builder-code invalidation be?

**Status:** RESOLVED.

Use package-wide project Python revision in v0.1. It may cause extra `build_required`, but it must not miss helper-code changes. Finer granularity is deferred.


### P3 / Q3.E10 — Content-stable receipt identity vs repeated activation history

**Status:** RESOLVED.

A receipt identifies *what exact dependency baseline/target/build evidence was validated*, so returning later to the identical evidence should reuse the same content-stable receipt ID. But a later re-activation after an intervening different receipt is still a new state transition and must not disappear from append-only history.

Decision: current selection comes from persisted dependency state, not receipt creation timestamps. Every real state mutation advances a monotonic `state_revision`; event identity includes that revision. Therefore exact retries stay idempotent, while A → B → A produces three history occurrences even though the first and third states reference the same receipt.

This is not an open product question and does not require user input. It is recorded here because the distinction between content identity and transition-occurrence identity is subtle and should remain discoverable.

### P4 / Q4.3 — Markdown section-level dependencies

**Status:** RESOLVED by user.

Do not support section-level Markdown dependencies in v0.1. If a dependency must target only part of a document, model that part as structured JSON and address the relevant field/object.

### P7 / Q7.3 — Synthetic scale/performance budget

**Status:** RESOLVED DEFAULT, currently non-blocking.

Start with a benchmark fixture around 10k resources / 50k dependency edges. Measure a baseline during hardening and turn it into an environment-normalized acceptance budget before final release acceptance.

### P7 / Q7.4 — Filesystem watch/daemon mode

**Status:** RESOLVED DEFAULT, non-blocking.

Explicit CLI commands remain canonical. Watch mode stays optional/out of acceptance unless evidence shows that explicit-command workflow is insufficient.

## Next-phase question scan

### P3 — Dependency receipts, baselines, comparators, diff and state

**Status: IMPLEMENTED / ACCEPTED.** Q3.1–Q3.8 and all P3 emergent questions are answered. No P3 user question remains open.

Resolved P3 emergent questions:

- **Q3.E1:** read-only dependency queries must not create `_dependency` directories.
- **Q3.E2:** unavailable dependency source or required builder produces `invalid`, not a semantic verdict.
- **Q3.E3:** `audit_complete=false` cannot be persisted as `valid`; it is `invalid` until an auditable build exists.
- **Q3.E4:** v0.1 does not invent virtual `field_set`/`collection` refs; aggregate builders persist multiple exact refs.
- **Q3.E5:** `status/history/graph` read persisted diagnostic state without requiring current builder imports.
- **Q3.E6:** stable logical `receipt_id` is paired with full persisted `receipt_hash` so retries remain idempotent while tampering is detectable.
- **Q3.E7:** explicit validation pins the exact target revision; editing the target itself requires re-review, and a missing target is invalid.
- **Q3.E8:** state/events must be cross-link explainable by their receipt, including changed-dependency membership and active-receipt identity.
- **Q3.E9:** persisted audit-critical receipt/event fields are parsed strictly; malformed primitive types are corruption, not coerced values.

The former P3 watch items are now implemented contracts: exact slices, separation of physical `source_hash` from semantic dependency version, builder-revision invalidation, comparator validation, canonical `data` for whole structured-resource dependencies, and no semantic inference from structural diffs.

### P4 — Semantic review

**Status: IMPLEMENTED / ACCEPTED.** Q4.1–Q4.4 and P4 emergent implementation questions are answered. No user-owned question remains open.

Resolved P4 emergent questions:

- **Q4.E1:** semantic `validate` requires the exact `review_context_id` from the reviewed packet so known target/dependency/rule changes after review are rejected.
- **Q4.E2:** current semantic target/source availability is checked at runtime, not during project-package import, preserving diagnostics when files disappear.
- **Q4.E3:** a newly registered semantic rule with no validated receipt appears in `check` as ephemeral `review_required`; no fake receipt/state is created.
- **Q4.E4:** initial validation uses `still-valid`; `updated` requires a previously validated target and an actual target revision change.
- **Q4.E5:** one exact whole target cannot simultaneously own deterministic-builder and semantic-review receipts while v0.1 state selects one active receipt per exact target.
- **Q4.E6:** semantic validation history may reference a dependency removed by a rule change; integrity resolves reviewed changes against prior + current receipts.
- **Q4.E7:** optional semantic receipt/event fields remain on persisted schema 1.0.0 because legacy P3 evidence remains readable.
- **Q4.E8:** review-context identity is occurrence-aware so recurrent content-stable A/B states are new semantic reviews rather than old retries.
- **Q4.E9:** semantic state classification follows the current rule dependency type, including `validity → stale` and rule-type transitions.
- **Q4.E10:** invalid semantic actor/ref CLI inputs remain inside the versioned JSON error protocol.

No new ambiguous/deferred policy point was promoted by P4. The existing A1–A5 items remain the discoverable deferred choices.

### P5 — Materialization and sync

**Status: IMPLEMENTED / ACCEPTED.** Q5.1–Q5.4 are answered and P5 emergent Q5.E1/Q5.E2 are resolved. No user-owned question remains open.

Resolved P5 emergent decisions:

- **Q5.E1:** mixed semantic↔deterministic SCCs use bounded sync; deterministic members run at most once per occurrence and semantic members remain `attention_required`.
- **Q5.E2:** removed/renamed materialization outputs are never auto-deleted; orphaned provenance is preserved and surfaced as attention work. An intentional ownership transition is completed explicitly with `materialize file://PATH --ack-orphan`, preserving file bytes and prior provenance while marking the record acknowledged.
- **Q5.E3:** orphan attention must have a supported non-destructive completion path; explicit acknowledgement preserves the record and sets `orphan_acknowledged=true`.
- **Q5.E4:** P3/P4 diagnostics do not depend on P5 renderer registration; renderers are loaded only for materialization/sync commands.

P5 remains accepted after post-axis correction; final dev11 handoff evidence is recorded in the P5 package audit. P6 was subsequently implemented and accepted.

### P7 — Hardening

**Status: IMPLEMENTED / ACCEPTED AFTER POST-AXIS AUDIT.** Q7.1–Q7.4 and Q7.E1–Q7.E11 are answered. No user-owned/blocking question remains unresolved.

Historical carried item: **DAX18 was partial at P7 acceptance under Q7.3/Q7.E8** and is now represented formally by `P7-CG1`. P8-A8 established the environment-normalized budget and passed it, so the carried gate is resolved. The P7 record remains historically partial rather than being retroactively rewritten as PASS.

Existing **A1** (trusted/cooperative project Python) remains deferred; P7 hardens engine-owned locking/transactions/recovery but does not sandbox arbitrary project callbacks.


- **Q7.E9 (resolved):** corrupt transaction journals fail closed before any recovery mutation.
- **Q7.E10 (resolved):** migration marker provenance must match the registered migration and validated released evidence.
- **Q7.E11 (resolved):** hardening audit logs are verified evidence; corruption blocks verify without crashing it.

### P8 — Final verification and handoff

Q8.1–Q8.4 are answered. P8 resolved the carried P7-CG1/P8-A8/DAX18 release gate. No user-owned question remains open.

## When to add a new question

Create an `emergent_question` in the relevant phase record when implementation evidence exposes a real choice that cannot be derived from an already accepted invariant. Do not manufacture a question merely because multiple implementations are imaginable.

A new user-owned question is justified only when the choice changes product semantics, documentation ownership, human/AI authority, or another user-facing contract. Pure implementation choices should normally be answered by the implementer and recorded with rationale/evidence.


### P6 — Complete CLI and AI/CI operating protocol

**Status: IMPLEMENTED / ACCEPTED.** All Q6.1–Q6.4 and Q6.E1–Q6.E5 are answered; no user-owned question remains open.

Resolved emergent points:

- **Q6.E1:** canonical envelope incompatibility is explicit via machine schema **2.0.0**.
- **Q6.E2:** read-only project extension loading suppresses Python bytecode writes.
- **Q6.E3:** verify independently release-gates documentation-owned required builders, not internal-only helpers.
- **Q6.E4:** verify aggregates component failures and continues independent checks instead of fail-fast.
- **Q6.E5:** the project Python package remains optional for plain documentation-only projects.
- **Q6.E6:** unsafe/corrupt dependency-runtime construction is a blocking `verify` finding/exit 3, not an internal crash.
- **Q6.E7:** explicit project roots must be existing directories; existing docs roots must be directories.
- **Q6.E8:** accidental project `SystemExit` is wrapped at import/registration/builder/renderer boundaries so JSON protocol remains intact.
- **Q6.E9:** human non-success output preserves diagnostic facts already present in the command result.
- **Q6.E10:** CLI registry/parser/exit-table parity is now enforced by an executable regression test.
- **Q6.E11:** verify uses canonical unavailable/incomplete-audit state semantics rather than a weaker parallel classifier.

No new ambiguous/deferred policy point was created by P6 or its post-acceptance audit. The cooperative project-code side-effect limitation remains existing **A1** and is an explicit post-v0.1 boundary. P7 and P8 are complete.


### P8 — Final release gate

**Status: IMPLEMENTED / ACCEPTED.** Q8.1–Q8.4 and Q8.E1–Q8.E4 are answered; no user-owned/blocking question remains.

- **Q8.E1 (answered, implementer):** performance is normalized by same-interpreter deterministic calibration; budget is stored before final rerun and every CPU/RSS/workload check is blocking.
- **Q8.E2 (answered, implementer):** `sample_project` preserves initial semantic-review onboarding state; P8 proves its clean lifecycle on a temporary copy rather than baking a semantic verdict into the fixture.

Existing A1 trusted/cooperative project Python remains an explicit v0.1 boundary, not an unresolved release question.
