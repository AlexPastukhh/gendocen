# P6 Post-Acceptance Independent Axis Review

Date: 2026-10-02

Decision: **P6 remains accepted after correction of confirmed post-acceptance defects.** No unresolved user-owned or blocking question remains before P7.

Runtime build after correction: **0.1.0.dev13**.

This review intentionally separates reproduced defects from deferred/ambiguous design points. It does not downgrade P6 merely because stronger P7 hardening is possible.

## Confirmed findings and corrections

### PA6-F001 — dependency-runtime construction corruption escaped complete `verify`

Reproduced: a symlinked documentation-owned `_dependency` root caused `verify --json` to fall through the generic internal boundary with exit `5`, so the promised complete verification report disappeared.

Correction:

- dependency-runtime construction failure is now a blocking `dependency_runtime_unavailable` finding;
- independent component/builder checks continue when possible;
- report remains schema-valid and returns exit `3`, not internal-error exit `5`.

Evidence: `src/docengine/verification.py`, P6 verify regression test, `plan/evidence/P6/postaxis/verify_dependency_runtime_symlink.json`.

### PA6-F002 — invalid explicit roots could verify as a clean empty project

Reproduced: a nonexistent `--project-root`, a regular file used as project root, or an existing regular file used as docs root could be accepted by discovery; `resources/status/verify` could then report success over an entity that was not a real project tree.

Correction:

- explicit project root must exist and be a directory;
- existing documentation root must be a directory;
- invalid root shape is usage/config exit `4`.

Evidence: `src/docengine/project.py`, `tests/test_project.py`, `plan/evidence/P6/postaxis/invalid_root_protocol.json`.

### PA6-F003 — project `SystemExit` could bypass the machine protocol

Reproduced: `SystemExit` from project package import/registration, builder execution or renderer execution escaped `Exception` boundaries and could terminate the process with stderr/no JSON envelope.

Correction:

- project import/registration, builder and renderer boundaries catch `SystemExit` specifically and convert it to normal engine component/domain errors;
- `KeyboardInterrupt` remains a real user interrupt and is not swallowed;
- `--json` now remains enveloped for these accidental project-code exits.

Evidence: `src/docengine/extensions.py`, `src/docengine/builders.py`, `src/docengine/materialization.py`, `tests/test_p6_protocol.py`, `plan/evidence/P6/postaxis/project_systemexit_protocol.json`.

### PA6-F004 — human non-success rendering could discard diagnostic facts

Reproduced: an invalid `status` result returned complete target/count evidence in JSON but human output collapsed to only `domain_failure` plus roots. `verify` usage/config errors likewise took the report renderer even when no report existed and could hide the actual issue message.

Correction:

- dependency/orchestration human rendering now preserves available data for non-success/attention results;
- verify uses the report renderer only when a report actually exists; otherwise normal issue rendering is used.

Evidence: `src/docengine/cli.py`, P6 human parity regressions, `plan/evidence/P6/postaxis/human_json_failure_parity.json`.

### PA6-F005 — `verify` had a weaker semantic-unavailable classifier than P3/P4 runtime semantics

Reproduced: removing a previously validated semantic rule produced `semantic_rule_unavailable`, but P6 current-check verification classified the target as `review_required` from the historical receipt type rather than canonical `invalid`.

Correction:

- current-check verification now treats incomplete audit or unavailable source/builder/target/semantic rule as `invalid`;
- only inspectable structural changes use dependency-type-derived stale/review/build states.

Evidence: `src/docengine/verification.py`, P6 regression test, `plan/evidence/P6/postaxis/semantic_rule_unavailable_verify.json`.

### PA6-F006 — claimed CLI registry/parser acceptance protection was not actually automated

The runtime registry and parser were manually compared and already matched, so there was **no current runtime mismatch**. However `docs/CLI_CONTRACT.md` stated acceptance tests compare them while the accepted v0.20 suite did not actually perform that comparison.

Correction:

- P6 regression now introspects the real argparse surface and checks command list, command-specific options and target cardinality against `CLI_COMMANDS.json`;
- frozen exit table is checked in the same assurance test.

Evidence: `tests/test_p6_protocol.py`, `plan/evidence/P6/postaxis/cli_registry_parser_parity.json`.

### PA6-F007 — active materialization documentation still called `verify` unimplemented

`docs/MATERIALIZATION_RUNTIME.md` still said `verify` remained P8 work and was intentionally unimplemented even though P6 implemented/accepted it.

Correction:

- active runtime docs now identify `verify` as implemented in P6 and distinguish it from P8 global release-gate consolidation;
- `tools/audit_spec.py` rejects the stale statement if it reappears.

## Axis conclusions after correction

| Axis | Result | Post-axis conclusion |
|---|---|---|
| DAX03 identity/schema/version integrity | PASS | Machine envelope remains explicitly versioned 2.0.0; report/schema behavior remains valid after corrections. |
| DAX04 path/data safety | PASS for exercised P6 slice | Explicit root shape is validated and unsafe dependency runtime roots become verification findings. |
| DAX08 invalidation/state semantics | PASS for exercised P6 slice | Verify now mirrors canonical unavailable/incomplete-audit status semantics. |
| DAX09 semantic review/agency | PASS | Verify remains read-only and never manufactures semantic acceptance. |
| DAX11 materialization parity/drift | PASS | Generated drift/orphan verification behavior unchanged and read-only. |
| DAX12 CLI boundaries | PASS | Failure/usage/project callback paths remain enveloped; human non-success surface retains diagnostics. |
| DAX13 AI/CI usability | PASS | Invalid roots, project callback exits and verify corruption remain machine-readable with stable exit classes. |
| DAX14 history/provenance/diagnostics | PASS | Dependency-runtime corruption produces complete available report; semantic-unavailable status is canonical. |
| DAX16 compatibility | PASS for P6 slice | Explicit machine schema 2.0.0 boundary remains unchanged. |
| DAX19 assurance | PASS | Reproduced defects plus registry/parser parity now have dedicated regression coverage. |
| DAX20 handoff integrity | PASS | Active docs are corrected; dev13 wheel/source parity, clean-venv protocol probes and manifest-only portable copy all pass. |

Global axis closure still belongs to P8.

## Ambiguous / deferred points

No new P6 ambiguity was created by this review.

The existing **A1 cooperative/trusted project-code boundary** remains a real deferred P7 hardening point: catching accidental `SystemExit` does not sandbox arbitrary project filesystem/network/process side effects. This review does not misclassify that known trust-model limitation as a new P6 defect.

P7 concurrency/transactionality/performance work also remains P7 scope rather than a P6 failure.

## Questions

No new user-owned or blocking question appeared.

Implementer-owned Q6.E6–Q6.E11 record the resolved decisions above. P7 pre-execution Q7.1–Q7.4 remain answered; P7 can start after the corrected P6 package is handed off.
