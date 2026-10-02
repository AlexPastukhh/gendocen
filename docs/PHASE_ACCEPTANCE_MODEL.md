# Phase Acceptance Model

Phase execution records are canonical under `plan/phase_records/P*_EXECUTION_RECORD.json` and validate against `spec/schemas/PHASE_EXECUTION_RECORD.schema.json`.

## Normal acceptance

An accepted phase must have:

- every blocking question answered;
- every acceptance criterion `pass` or `not_applicable`;
- every mapped axis review `pass` or `not_applicable`.

A phase-local PASS closes only the risk slice exercised by that phase. P8 performs global release consolidation.

## Explicit carried release gates

A phase may exceptionally retain a **historical `partial`** criterion/axis at phase acceptance only when the record contains a matching `carried_release_gate` that names:

- the exact source criterion;
- the exact axis;
- a concrete later target phase;
- a concrete target criterion in that phase.

This is not a waiver. While the carry is `open`, final release is blocked. The carry becomes `resolved` only when the target phase is accepted, the target criterion is `pass`, and that target phase has a `pass` review for the carried axis.

The source phase keeps its historical `partial` status; it is not retroactively rewritten to PASS.

### P7 → P8 instance

`P7-CG1` carries historical `P7-A5 / DAX18` to `P8-A8`. P8 established the environment-normalized performance budget, reran the declared benchmark and passed P8/DAX18. Therefore `P7-CG1` is resolved before final release.

## Machine enforcement

`tools/audit_axes.py` enforces the model and rejects:

- accepted phases with uncarried partial criteria/axes;
- malformed/mismatched carry source or target identities;
- a carry claimed resolved without target criterion/axis PASS;
- any open carried gate at final P8 release;
- missing path-like evidence references.

`tools/audit_spec.py` invokes the same canonical auditor so spec/package self-audit cannot silently diverge from release-axis semantics.
