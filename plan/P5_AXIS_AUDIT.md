# P5 DAX Audit

Date: 2026-10-02
Decision: **PASS for P5 scope**. Global release-axis closure remains P8.

| Axis | P5 result | Evidence / boundary |
|---|---|---|
| DAX02 Documentation ownership/layout | PASS | Generated ownership comes only from `$docengine.materialize[]`; removed targets are preserved and surfaced as orphaned state. |
| DAX03 Identity/schema/version integrity | PASS | Materialization state schema, owner/renderer revisions, input revisions and SHA-256 output digests. |
| DAX04 Path confinement/data safety | PASS | Documentation-root confinement, reserved-tree protection, unowned-file rejection and symlink tests. |
| DAX06 Dependency capture/granularity | PASS | Sync rebuild selection follows P3 exact receipts and only affected generated inputs are refreshed. |
| DAX08 Invalidation/state semantics | PASS | Build-required targets rebuild; semantic review remains non-valid; bounded mixed SCC cannot loop automatically. |
| DAX09 Semantic review/human-AI agency | PASS | Sync never calls semantic `validate` and does not modify semantic target content. |
| DAX10 Determinism/idempotency | PASS | No-change repeat sync produces no rebuild/event/output/state churn. |
| DAX11 Materialization/view parity | PASS | Delete/recreate, drift detection, full regeneration and custom renderer tests. |
| DAX12 CLI contract/boundaries | PASS for P5 slice | `rebuild/materialize/sync` operational; failures remain envelope errors. P6 freezes final exit codes. |
| DAX13 AI/CI protocol | PASS for P5 slice | JSON surfaces expose affected work and `attention_required`; final envelope vocabulary is P6. |
| DAX14 Provenance/diagnostics | PASS | Generated output digest/provenance and orphan records remain inspectable. |
| DAX17 Domain independence/extensibility | PASS | Product/tax fixture and project-defined renderer run without core domain changes. |
| DAX19 Test assurance | PASS | Acceptance, negative, safety, drift, SCC, retry and CLI coverage. |
| DAX20 Release/handoff integrity | PASS | dev11 post-axis wheel/source parity, clean-venv corrected P5 workflow, manifest integrity and final portable-copy/ZIP gate. |

## Not classified as defects

- Project renderers are ordinary trusted/cooperative Python, consistent with the existing builder trust model.
- Removed materialization targets are not automatically deleted; this is a deliberate safety policy, not incomplete cleanup.
- `sync --all` means full **view regeneration**, not “re-run every deterministic builder regardless of evidence”; current derived values are still recomputed for rendering when needed.
- P6, not P5, freezes the final machine envelope and exit-code matrix.


## Post-acceptance corrections

Independent re-audit found and corrected P5 evidence/state/repairability/CLI defects. Canonical details are in `P5_POST_ACCEPTANCE_AXIS_REVIEW.md`. After correction, all mapped runtime axes pass for the P5 slice; DAX20 is re-established only after the dev11 frozen-package gate.
