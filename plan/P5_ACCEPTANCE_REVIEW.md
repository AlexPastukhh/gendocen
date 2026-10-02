# P5 Acceptance Review — Renderers, materialization, drift detection and sync

Date: 2026-10-02
Decision: **ACCEPTED**
Runtime build: **0.1.0.dev11**
Next phase: **P6 — Complete CLI and AI/CI operating protocol**

## Implemented

- deterministic renderer registry with built-in Markdown renderer and optional project renderers;
- output ownership exclusively from `$docengine.materialize[]`;
- documentation-owned materialization digest/provenance state;
- raw and derived resource materialization;
- generated-view drift/missing/outdated detection;
- clean full regeneration via `materialize --all`;
- deterministic `rebuild TARGET`;
- affected-only `sync` plus explicit `sync --all` full view regeneration;
- semantic `review_required`/`stale` preservation;
- bounded mixed semantic↔deterministic SCC handling;
- non-destructive orphan materialization handling;
- idempotent repeat sync without output/event/state churn.

P5 intentionally does not implement the final read-only `verify` release gate, multi-file transaction/locking, migration framework or final frozen CLI/exit-code contract. Those remain P6–P8 work.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| P5-A1 delete/recreate managed Markdown | PASS | P5 materialization tests + bundled generated examples |
| P5-A2 ownership/path safety | PASS | unowned-file, symlink and orphan-preservation tests |
| P5-A3 affected-only sync | PASS | `plan/evidence/P5/affected_sync.json` |
| P5-A4 semantic review remains unresolved | PASS | `semantic_attention.json`, mixed-SCC test/evidence |
| P5-A5 drift detection + clean regeneration | PASS | `drift_repair.json` |
| P5-A6 repeat sync idempotency | PASS | affected-sync repeat evidence |
| P5-A7 versioned materialization provenance | PASS | schema + example state files |
| P5-A8 JSON operational surfaces | PASS | P5 CLI tests |
| P5-A9 domain-independent/project renderer | PASS | product/tax fixture + custom renderer test |
| P5-A10 package/handoff integrity | PASS | `plan/P5_PACKAGE_AUDIT.md`, clean-venv evidence, final manifest/archive gate |

## Real issue found and corrected during P5 review

A malformed project `register_renderers` implementation could escape P3/P4 diagnostic commands as an uncaught P5 exception. The common CLI boundary now catches materialization/renderer errors so `check/explain/validate/materialize/sync` stay inside the machine-readable error protocol.

## Resolved implementation questions

- **Q5.E1:** mixed semantic↔deterministic SCCs use bounded sync. Deterministic members run at most once per occurrence; semantic members remain unresolved; affected mixed SCCs return `attention_required`; pure deterministic executable cycles remain errors.
- **Q5.E2:** removed/renamed materialization targets are never auto-deleted. Former output/provenance is reported as orphaned attention work because ownership may have become plain/canonical Markdown.

No new blocking or user-owned question remains before P6.


## Post-acceptance re-audit addendum

An independent P5 axis review reproduced additional correctness/repairability/protocol defects after initial acceptance. They are corrected in dev11 and regression-covered: stale/invalid derived materialization is blocked; `sync_failed` performs no generated-view writes; orphan attention has explicit provenance-preserving acknowledgement; materialization state parsing/symlink safety is strict; builder/renderer registration errors remain in JSON envelopes; dependency diagnostics no longer depend on P5 renderer registration; CLI help matches acknowledgement semantics.

No unresolved user-owned/blocking question remains. Q5.E3 and Q5.E4 are answered implementer decisions. See `P5_POST_ACCEPTANCE_AXIS_REVIEW.md`.
