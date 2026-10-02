# P4 Package Audit — post-axis dev9 final

Date: 2026-10-02
Decision: **PASS**
Runtime distribution: **0.1.0.dev9**
Specification/runtime package: **0.17.0-p4-postaxis-audited-final**

This package supersedes the dev8 P4 handoff after an independent post-acceptance axis audit reproduced and corrected semantic recurrence/state/CLI protocol defects.

## Final observed results

Frozen source/runtime checks:

- active wheel: exactly `generic_documentation_engine-0.1.0.dev9-py3-none-any.whl`;
- wheel METADATA version: `0.1.0.dev9`;
- full source-checkout suite after interim dev9 manifest: **149 passed, 177 subtests passed**;
- `python tools/audit_spec.py`: **SPEC AUDIT OK** after tests and after `compileall`;
- clean-venv wheel install: PASS;
- `pip check`: PASS;
- installed `docengine --version`: `0.1.0.dev9`;
- installed semantic smoke: upstream change → `review_required` → `explain` → `validate still-valid` → `valid`;
- installed `history`, `check`, and `graph`: PASS;
- invalid actor kind and malformed target ref: non-zero command result with versioned JSON error envelope and empty stderr;
- wheel/source runtime parity: **17/17 Python modules byte-for-byte identical**.

Portable manifest-only probe:

- copied exactly current manifest-tracked files plus `MANIFEST.json`;
- pre-test self-audit: **SPEC AUDIT OK**;
- full portable-copy suite: **149 passed, 177 subtests passed**;
- post-test self-audit: **SPEC AUDIT OK**;
- manifest hashes: **273/273 PASS**.

The final accepted copy/ZIP is rebuilt once more after this report is frozen so this report itself is included in the final manifest. No source/semantic changes are permitted after this point.

## Evidence

Primary dev9 final evidence:

- `plan/evidence/P4/post_axis_final/clean_venv_install.txt`
- `plan/evidence/P4/post_axis_final/clean_venv_pip_check.txt`
- `plan/evidence/P4/post_axis_final/clean_venv_version.txt`
- `plan/evidence/P4/post_axis_final/installed_check_before_validate.json`
- `plan/evidence/P4/post_axis_final/installed_explain.json`
- `plan/evidence/P4/post_axis_final/installed_validate_still_valid.json`
- `plan/evidence/P4/post_axis_final/installed_history.json`
- `plan/evidence/P4/post_axis_final/installed_check_after_validate.json`
- `plan/evidence/P4/post_axis_final/installed_graph.json`
- `plan/evidence/P4/post_axis_final/invalid_actor_envelope.json`
- `plan/evidence/P4/post_axis_final/invalid_target_envelope.json`
- `plan/evidence/P4/post_axis_final/smoke_assertions.txt`
- `plan/evidence/P4/post_axis_final/wheel_source_parity.txt`
- `plan/evidence/P4/post_axis_final/wheel_sha256.txt`
- `plan/evidence/P4/post_axis_final/full_test_summary.txt`
- `plan/evidence/P4/post_axis_final/spec_audit_after_tests.txt`
- `plan/evidence/P4/post_axis_final/spec_audit_after_compile.txt`

Post-axis defect reproduction evidence remains in `plan/evidence/P4/post_axis_audit/`.

## Handoff conclusion

P4 is accepted for its implemented scope. Global release-gate closure remains P8. The only newly identified unresolved design point is the non-blocking P5 mixed semantic↔deterministic cycle question recorded as `Q5.E1`; it is not classified as a P4 defect.
