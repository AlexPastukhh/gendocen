# Planning File Map

- `../OPEN_QUESTIONS_AND_AMBIGUITIES.md` — top-level discoverable index of ambiguous/deferred policy points and non-blocking questions; canonical decisions still live in phase records.

- `IMPLEMENTATION_PLAN.md` — human-readable P0–P8 sequence.
- `ACCEPTANCE_AXES.md` — DAX01–DAX20 acceptance framework.
- `PHASE_EXECUTION_MODEL.md` — lifecycle/questions/evidence rules.
- `QUESTIONS_AND_DECISIONS.md` — human view of phase questions.
- `ACCEPTANCE_AND_OPEN_QUESTIONS.md` — adopted principles + navigation.
- `phase_records/P<n>_EXECUTION_RECORD.json` — canonical per-phase plan, questions/answers, evidence and acceptance result.
- `../spec/registries/ACCEPTANCE_AXES.json` — machine-readable axes.
- `../spec/schemas/PHASE_EXECUTION_RECORD.schema.json` — record schema.

- `PLAN_AUDIT.md` — findings/fixes from the plan consistency audit.
- `../tools/audit_spec.py` — executable self-audit for schemas, mappings, coverage, gates and manifest.

- `P0_ACCEPTANCE_REVIEW.md` — P0 implementation/acceptance review and evidence summary.
- `evidence/P0/` — P0 test, clean-install and CLI-envelope evidence.
- `../pyproject.toml` — installable runtime package metadata and console entry point.
- `../tests/` — runtime/contract test harness introduced in P0.
- `../dist/` — prebuilt wheel used for clean-environment distribution acceptance.

## Implemented phase artifacts

- `P1_ACCEPTANCE_REVIEW.md`, `P1_AXIS_AUDIT.md`, `P1_POST_ACCEPTANCE_AXIS_REVIEW.md`, `P1_PACKAGE_AUDIT.md` — accepted P1 evidence/audits.
- `P2_ACCEPTANCE_REVIEW.md` — P2 implementation and criterion acceptance.
- `P2_AXIS_AUDIT.md` — independent DAX02/03/04/05/06/10/14/17/19/20 review for P2 scope.
- `P2_PACKAGE_AUDIT.md` — final wheel/source/manifest/handoff checks for P2.
- `evidence/P2/` — clean-venv, sample build, unrelated-domain build and cycle diagnostic evidence.
- `../docs/BUILD_RUNTIME.md` — concrete P2 builder/derived/tracked-read contract.
- `../src/docengine/builders.py` — generic P2 builder runtime.
- `../src/docengine/extensions.py` — confined project-package loader.
- `../spec/schemas/DERIVED_OBJECT.schema.json` — serializable derived/provenance envelope.
- `../examples/product_tax_project/` — non-research synthetic P2 fixture.

## P3 implemented phase artifacts

- `P3_ACCEPTANCE_REVIEW.md` — P3 implementation and criterion acceptance.
- `P3_AXIS_AUDIT.md` — phase-local DAX review for the dependency persistence/query slice.
- `P3_PACKAGE_AUDIT.md` — final wheel/source/manifest/handoff checks for P3.
- `evidence/P3/` — regression, CLI, integrity, clean-install and package evidence.
- `../docs/DEPENDENCY_RUNTIME.md` — concrete P3 baseline/receipt/state/event/diff contract.
- `../src/docengine/dependencies.py` — generic P3 dependency runtime.
- `../spec/schemas/BASELINE_SNAPSHOT.schema.json` — content-addressed baseline envelope.
- `../spec/schemas/DEPENDENCY_RECEIPT.schema.json` — persisted receipt contract.
- `../spec/schemas/DEPENDENCY_STATE.schema.json` — current dependency-state contract.
- `../spec/schemas/DEPENDENCY_EVENT.schema.json` — append-only dependency-event contract.

## P4 implemented phase artifacts

- `P4_ACCEPTANCE_REVIEW.md` — P4 semantic-review criterion acceptance.
- `P4_AXIS_AUDIT.md` — phase-local DAX review for semantic rules/review/validation.
- `P4_PACKAGE_AUDIT.md` — final dev9 post-axis wheel/source/manifest/handoff checks.
- `evidence/P4/` — review-packet, still-valid, updated, stale-context, rule-change, integrity and installed-CLI evidence.
- `../docs/SEMANTIC_REVIEW.md` — concrete P4 semantic review/validation contract.
- `../src/docengine/semantic.py` — semantic rule registry and review runtime.
- `../spec/schemas/REVIEW_PACKET.schema.json` — machine-readable review packet contract.

- `P4_POST_ACCEPTANCE_AXIS_REVIEW.md` — independent P4 post-acceptance axis review, confirmed fixes and deliberately deferred adjacent risks.


## P5 implemented phase artifacts

- `P5_ACCEPTANCE_REVIEW.md` — P5 implementation/criterion review.
- `P5_AXIS_AUDIT.md` — independent phase-local DAX review.
- `P5_PACKAGE_AUDIT.md` — final dev10 wheel/manifest/handoff evidence.
- `evidence/P5/` — affected sync, drift, semantic attention, mixed SCC, orphan and installed-package evidence.
- `../docs/MATERIALIZATION_RUNTIME.md` — P5 renderer/materialization/sync contract.
- `../src/docengine/materialization.py` — generic P5 runtime.
- `../spec/schemas/MATERIALIZATION_STATE.schema.json` — generated-view provenance state contract.

- `P5_POST_ACCEPTANCE_AXIS_REVIEW.md` — independent post-acceptance P5 DAX re-audit, reproduced defects, corrections, ambiguities and questions.


## P6 implemented phase artifacts

- `P6_ACCEPTANCE_REVIEW.md` — P6 criteria and defect closure.
- `P6_AXIS_AUDIT.md` — phase-local protocol/verify DAX review.
- `P6_PACKAGE_AUDIT.md` — final dev12 distribution/handoff gate.
- `evidence/P6/` — fresh-agent workflow and verify evidence.
- `../docs/CLI_CONTRACT.md` — frozen envelope/exit/command boundary contract.
- `../docs/AI_USAGE_PROTOCOL.md` — fresh AI/CI operating runbook.
- `../src/docengine/verification.py` — read-only complete verification runtime.
- `../spec/schemas/CLI_OUTPUT.schema.json` — canonical machine envelope schema 2.0.0.
- `../spec/schemas/VERIFICATION_REPORT.schema.json` — verify report contract.


## P7 implemented phase artifacts

- `P7_ACCEPTANCE_REVIEW.md` — P7 criteria, defects and deliberate partial performance gate.
- `P7_AXIS_AUDIT.md` — DAX14/15/16/18/19/20 phase-local review.
- `P7_POST_ACCEPTANCE_AXIS_REVIEW.md` — independent post-acceptance P7 DAX re-audit, reproduced defects, corrections and portability watch item.
- `P7_PACKAGE_AUDIT.md` — final dev14 distribution/handoff gate.
- `evidence/P7/benchmark_10k_50k.json` — declared synthetic baseline.
- `../docs/HARDENING_RUNTIME.md` — locking/transaction/recovery contract.
- `../docs/MIGRATIONS.md` — persistence migration contract.
- `../src/docengine/hardening.py` — P7 hardening runtime.
- `../spec/registries/MIGRATIONS.json` — registered runtime migration surface.

- `P7_POST_ACCEPTANCE_AXIS_REVIEW.md` — independent post-acceptance P7 DAX re-audit and correction evidence.


## P8 final release artifacts

- `P8_ACCEPTANCE_REVIEW.md` — final phase criteria review.
- `P8_FINAL_AXIS_AUDIT.md` — global 20-axis consolidation.
- `P8_PACKAGE_AUDIT.md` — final wheel/archive/portable-copy evidence.
- `evidence/P8/` — performance and lifecycle evidence.
- `../docs/RELEASE_GATE.md` — release tooling and policy.
- `../tools/release_manifest.py` — deterministic engine manifest generate/validate.
- `../tools/audit_axes.py` — canonical global axis closure.
- `../tools/release_check.py` — clean bundled-fixture lifecycle.
- `../tools/benchmark_release.py` — normalized DAX18 release benchmark.

- `P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md` — independent all-axis consistency re-audit and v0.25 correction set.
- `../docs/PHASE_ACCEPTANCE_MODEL.md` — formal accepted/partial carried-release-gate semantics.


## Repository persistence artifacts

- `REPOSITORY_PERSISTENCE_AUDIT.md` — v0.26 Git persistence defect/correction/acceptance record.
- `../docs/REPOSITORY_WORKFLOW.md` — bootstrap, development, evidence, manifest, version/tag and private-repository contract.
- `../.gitignore`, `../.gitattributes`, `../.editorconfig` — repository hygiene and line-ending controls.
- `../.github/workflows/ci.yml` — ordinary PR/push regression/audit/clean-worktree gate.
- `../.github/workflows/release-gate.yml` — tag/manual full release/performance gate.

- `WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md` — v0.27 Windows/Python 3.14 repository portability defects, corrections and acceptance evidence.
