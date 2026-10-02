# P5 Package Audit — post-axis dev11 final

Date: 2026-10-02
Decision: **PASS**
Runtime distribution: **0.1.0.dev11**
Specification/runtime package: **0.19.0-p5-postaxis-audited-final**

This report supersedes the initial dev10 P5 package gate after an independent post-acceptance axis review reproduced and corrected additional P5 materialization/state/repairability/CLI defects.

## Final observed checks

- targeted post-axis regressions: **8 passed, 6 subtests passed**;
- complete P5 targeted suite: **24 passed, 9 subtests passed**;
- full source-checkout suite: **173 passed, 193 subtests passed**;
- `python tools/audit_spec.py`: **SPEC AUDIT OK** before/after full tests and after `compileall`;
- active wheel: exactly `generic_documentation_engine-0.1.0.dev11-py3-none-any.whl`;
- wheel SHA-256: `47c31c0dfc95a3b628651efebfd2aba3e813abbe5b7e4fd647f7da722f92581f`;
- wheel METADATA/runtime version: **0.1.0.dev11**;
- wheel/source parity: **18/18 runtime Python modules identical**;
- clean-venv install: **PASS**;
- `pip check`: **No broken requirements found**;
- installed `docengine --version`: **0.1.0.dev11**;
- installed stale-derived direct materialization: **rejected in JSON envelope, exit 2**;
- installed orphan workflow: **attention_required → `--ack-orphan` → ok**, preserving file/provenance;
- installed dependency diagnostic with broken renderer registration: **check remains ok**;
- installed materialization with broken renderer registration: **machine-readable failure, exit 2**;
- manifest-only portable probe: **173 passed, 193 subtests passed**, **SPEC AUDIT OK**, **343/343 tracked hashes match**;
- evidence: `plan/evidence/P5/post_axis_audit/` and `plan/evidence/P5/post_axis_final/`.

## Transferability gate

The final accepted directory/ZIP is built only from the frozen final manifest. No source/documentation changes are made after this report; the handoff step re-runs tests/self-audit on that manifest-only copy and requires exact ZIP member equality/CRC.
