# P5 Post-Acceptance Axis Review

Date: 2026-10-02
Decision: **PASS after corrections for the P5 risk slice**
Runtime correction candidate: **0.1.0.dev11**
Package correction candidate: **0.19.0-p5-postaxis-audited-final**

## Review method

This review did not trust the existing P5 `PASS` labels. Each mapped P5 axis was re-read against executable behavior, with targeted probes for cross-phase state/materialization/CLI interactions. A point is called a defect only when runtime behavior contradicts an accepted contract/axis or makes the supported workflow unsafe/unrepairable.

## Confirmed problems found and corrected

### R1 — Direct derived materialization could advance the view ahead of dependency evidence

A derived target could be rebuilt in-memory by `materialize` after its upstream dependency changed, even though the persisted build receipt/state still represented the old validated build. That allowed generated Markdown to move ahead of dependency evidence.

**Correction:** derived materialization now requires an active, audit-complete, `valid` receipt whose dependency diff is unchanged and whose recorded output digest matches the newly built object. Otherwise materialization refuses and requires rebuild/check.

**Axes:** DAX08, DAX11, DAX14.

### R2 — `sync_failed` could write a view from audit-incomplete derived output

When a rebuild produced `audit_complete=false`, sync could learn that the target was invalid but still proceed into materialization before returning failure.

**Correction:** sync now computes final invalid/build-required state before any view writes. `sync_failed` returns zero materialization writes.

**Axes:** DAX08, DAX09, DAX11.

### R3 — Safe orphan policy had no supported completion path

P5 correctly refused to auto-delete an old generated file after ownership metadata was removed, but unresolved orphan attention could persist forever because normal workflow forbids manual machine-state editing.

**Correction:** `materialize file://PATH --ack-orphan` explicitly acknowledges the ownership transition while preserving the file and all previous owner/renderer/input/output provenance. The persisted record gains `orphan_acknowledged=true`; later sync reports it as acknowledged rather than unresolved attention.

**Axes:** DAX12, DAX13, DAX14.

### R4 — Materialization-state parser was weaker than its JSON Schema

Runtime loading accepted a schema-invalid `resource_kind` value.

**Correction:** audit-critical materialization state fields are parsed strictly, including the `managed|derived` resource-kind contract and canonical output/owner identity.

**Axes:** DAX03, DAX14.

### R5 — Materialization machine-state path could traverse a symlinked state directory

A symlinked `docs/_dependency/state` redirect inside documentation space was not consistently rejected by the P5 state layer.

**Correction:** materialization state initialization rejects symlink components in dependency/state ownership paths and refuses state-file symlinks on read/write.

**Axis:** DAX04.

### R6 — Builder registration errors could escape the JSON CLI contract

A malformed duplicate builder registration could escape current P5/diagnostic command boundaries instead of returning the common machine-readable error envelope.

**Correction:** component registration failures are caught at CLI boundaries and returned as versioned command errors.

**Axes:** DAX12, DAX13.

### R7 — Broken P5 renderer registration could block older P3/P4 diagnostics

`check/diff/explain` do not require renderers, but extension loading could invoke a broken `register_renderers` and make persisted dependency/semantic diagnostics unavailable.

**Correction:** renderer registration is loaded only for commands that need materialization/rendering. Older dependency/semantic diagnostic paths remain available independently.

**Axes:** DAX12, DAX13, DAX14.

### R8 — `--ack-orphan` help text contradicted the corrected provenance semantics

CLI help said acknowledgment would “forget” provenance while implementation deliberately preserves it.

**Correction:** CLI help and handoff docs now explicitly say acknowledgment preserves the file and provenance.

**Axes:** DAX12, DAX20.

## Axis result after correction

| Axis | Post-axis result | Notes |
|---|---|---|
| DAX02 Documentation ownership/layout | PASS | Ownership remains declared only in `$docengine.materialize[]`; orphan transition is explicit and non-destructive. |
| DAX03 Identity/schema/version integrity | PASS | Materialization-state runtime parser now matches schema-critical identity/type constraints. |
| DAX04 Path confinement/data safety | PASS | Generated outputs and machine materialization state both reject symlink/path escapes. |
| DAX06 Dependency capture/granularity | PASS | Affected sync still follows exact P3 dependency evidence; no issue found. |
| DAX08 Invalidation/state semantics | PASS after R1/R2 | View generation can no longer outrun stale/invalid dependency evidence. |
| DAX09 Semantic review/agency | PASS | Failed/attention sync never fabricates semantic acceptance or writes invalid derived views. |
| DAX10 Determinism/idempotency | PASS | No-change sync/materialize behavior remains stable; no issue found. |
| DAX11 Materialization/view parity | PASS after R1/R2 | Derived output parity is gated by current valid build evidence. |
| DAX12 CLI contract/boundaries | PASS after R3/R6/R8 | Orphan acknowledgment is official; registration failures remain envelopes; help matches behavior. |
| DAX13 AI/CI protocol | PASS after R3/R6/R7 | Repair and diagnostic workflows are machine-readable and component-scoped. |
| DAX14 Provenance/diagnostics | PASS after R1/R3/R4/R7 | Orphan provenance is retained; state parsing/cross-phase diagnostics remain explainable. |
| DAX17 Domain independence/extensibility | PASS | Product/tax and custom-renderer fixtures still use unchanged core. |
| DAX19 Test assurance | PASS | New regressions cover every reproduced post-axis defect. |
| DAX20 Release/handoff integrity | PASS | dev11 wheel/source parity, clean-venv corrected workflows and manifest-only portable probe pass; final ZIP is built from the same frozen manifest. |

## Ambiguous / policy-sensitive points

No new unresolved P5 ambiguity was discovered by this audit.

The existing trust/hardening ambiguities A1–A5 remain unchanged. Mixed semantic↔deterministic SCC semantics (A6/Q5.E1) are already resolved in P5. Crash-safe multi-file transactions/locking remain explicitly P7 scope and are not reclassified as a P5 defect.

## Questions produced by this audit

No new user-owned or blocking question appeared.

Two implementer-owned questions were made explicit and resolved:

- **Q5.E3:** how to resolve orphan attention safely → explicit provenance-preserving `--ack-orphan`.
- **Q5.E4:** whether P3/P4 diagnostics should depend on P5 renderer registration → no; renderer loading is component-scoped.

P6–P8 records contain no unresolved pending/blocking question at this point.

## Evidence

- `tests/test_p5_materialization.py::P5PostAxisRegressionTests`
- `plan/evidence/P5/post_axis_audit/regression_tests.txt`
- `plan/evidence/P5/post_axis_audit/full_functional_tests.txt`
- `plan/evidence/P5/post_axis_audit/materialize_help.txt`

Final distribution evidence is recorded in `P5_PACKAGE_AUDIT.md`; the dev11 portable-copy gate passed.
