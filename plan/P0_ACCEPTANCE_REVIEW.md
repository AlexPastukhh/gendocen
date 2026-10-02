# P0 Acceptance Review — Executable foundation, contracts and test harness

Date: 2026-10-02
Decision: **ACCEPTED**
Next phase: **P1 — Project, resource, storage and loader core**

## Implemented

- installable Python package (`pyproject.toml`) for Python >=3.11;
- `docengine` console entry point with all contracted command names present;
- engine/persisted-state/machine-output version constants;
- one stable JSON result envelope for every CLI command;
- read-only project/documentation-root discovery foundation;
- path-confinement helper rejecting traversal outside a configured root;
- generic/domain-neutral core protocols;
- unit, contract, CLI, path-safety and sample-fixture tests;
- wheel distribution artifact and clean-venv installation check.

P0 intentionally does **not** implement managed-resource loading, dependency evaluation, builders, materialization, or semantic validation.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| P0-A1 clean install/import/help | PASS | `dist/*.whl`, `plan/evidence/P0/clean_venv_install.txt`, `clean_venv_help.txt` |
| P0-A2 common versioned JSON envelope | PASS | `src/docengine/output.py`, `tests/test_cli.py`, `installed_cli_envelopes.json` |
| P0-A3 safe root discovery / no writes | PASS | `src/docengine/project.py`, `tests/test_project.py` |
| P0-A4 domain-neutral core | PASS | `tests/test_domain_neutrality.py` |
| P0-A5 registry/schema contract tests + malformed failures | PASS | `tests/test_spec_contracts.py`, `unit_tests.txt` |
| P0-A6 handoff docs accurately show P0 accepted / P1 next | PASS | `README.md`, `START_HERE_AGENT.md` |

## DAX review

All mapped P0 axes pass **for P0 scope**: DAX01, DAX03, DAX04, DAX12, DAX13, DAX17, DAX19, DAX20. This does not close those engine-wide axes globally; `plan/P0_AXIS_AUDIT.md` records global progress as PARTIAL after P0 and P8 performs final consolidated closure.

A post-acceptance review found one DAX20 defect: normal test execution created transient cache files that the old manifest audit treated as canonical package additions. `tools/audit_spec.py` now ignores a narrow explicit transient set and `tests/test_audit_hygiene.py` prevents regression.

## Emergent implementation decision

A clean Python 3.13 venv in this environment does not contain `setuptools`, so an offline source-tree PEP 517 install cannot load the build backend. This does not justify adding build tooling to runtime dependencies. Consistent with the pre-existing P0 decision (“editable install for development, wheel for distribution”), clean-environment acceptance builds the wheel in the build environment and installs that prebuilt wheel into a fresh venv with no runtime dependencies.

## Evidence summary

- source test suite: 13/13 PASS;
- clean venv wheel install: PASS;
- clean venv `pip check`: PASS;
- clean venv `docengine --help`: PASS;
- all 13 command stubs emit the same machine-output envelope schema: PASS;
- malformed JSON and malformed use-case registry negative tests: PASS;
- path traversal/explicit outside-doc-root rejection: PASS.
