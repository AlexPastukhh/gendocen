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

- `GITHUB_CHECKOUT_PORTABILITY_AUDIT.md` — v0.28 post-push fresh-checkout integrity/path-identity defects, corrections, regression coverage and release evidence.

## v0.29 documentation/workflow normalization artifacts

- `DOCUMENTATION_WORKFLOWS_EXECUTION.md` — post-P8 documentation/use-case normalization execution record; historical phase records remain unchanged.
- `../docs/CORE_WORKFLOWS.md` — real-life authoring/inspection/hardening workflows composed from atomic DOCxx contracts.
- `../spec/registries/USE_CASE_COVERAGE_AMENDMENTS.json` — additive mapping for post-acceptance atomic use cases naming already-implemented historical capabilities.
- `../spec/schemas/USE_CASE_COVERAGE_AMENDMENTS.schema.json` — schema for additive coverage amendments.
- `../tests/test_documentation_workflows.py` — workflow-reference, CLI coverage, mirrored authoring and runnable selective-invalidation checks.


## v0.30 independent-review correction artifacts

- `plan/DOCUMENTATION_WORKFLOWS_POST_REVIEW_CORRECTION.md` — additive record for the independent-review fixes applied after v0.29.
- `tests/test_documentation_workflows.py` — adversarial regression coverage for semantic mirror authority, ownership classification, registration proof, semantic tutorial sequence, onboarding consistency, and future-helper guards.

## v0.31 clean-chat onboarding correction artifacts

- `../docs/CLEAN_CHAT_QUICKSTART.md` — zero-context environment/project-root/trust/ownership/task-routing entrypoint for a new human/AI session.
- `CLEAN_CHAT_ONBOARDING_CORRECTION.md` — additive execution/scope record for the v0.31 onboarding correction.
- `../tests/test_documentation_workflows.py` — clean-chat route/preflight regression coverage, including proof that `resources` inventory does not import project extensions.

## v0.32 clean-chat bootstrap finalization artifacts

- `../docs/CLEAN_CHAT_QUICKSTART.md` — adds bundled-wheel offline runtime bootstrap and root-explicit final command examples.
- `CLEAN_CHAT_BOOTSTRAP_FINALIZATION.md` — additive execution/scope record for the v0.32 correction.
- `../tests/test_documentation_workflows.py` — regression coverage for offline bootstrap documentation and explicit-root command examples.

## v0.33 explicit-root consistency artifacts

- `CLEAN_CHAT_EXPLICIT_ROOT_CORRECTION.md` — additive execution/scope record for the v0.33 root-selection correction.
- `../docs/CORE_WORKFLOWS.md`, `../docs/AI_USAGE_PROTOCOL.md`, and runnable example READMEs — explicit-root project-command guidance.
- `../tests/test_documentation_workflows.py` — two-project and nested-init root-selection regressions.

## v0.34 root-context closure artifacts

- `CLEAN_CHAT_ROOT_CONTEXT_CLOSURE.md` — additive execution/scope record for downstream root-context closure.
- `../examples/sample_project/README.md` — establishes disposable fixture cwd before `--project-root .`.
- `../tests/test_documentation_workflows.py` — inline/diagram command and fixture-ordering regression coverage.

## v0.35 root-guard hardening artifacts

- `CLEAN_CHAT_ROOT_GUARD_HARDENING.md` — additive record for compound/plain-prose root-guard hardening.
- `../tests/test_documentation_workflows.py` — per-command `&&` / `||` / `;`, prose and multiline root-guard regressions.

## v0.36 documentation consistency finalization artifacts

- `WORKFLOW_SCENARIO_TEMPLATE_BASELINE_AMENDMENT.md` — additive refinement of the original identical-heading scenario-template requirement into a semantic minimum; the historical pre-work baseline is not rewritten.
- `DOCUMENTATION_CONSISTENCY_FINALIZATION.md` — additive execution/scope record for current identity, WF03 baseline-example, scenario-template and root-option guard finalization.
- `../docs/CORE_WORKFLOWS.md` — exact baseline `A.field3 + B.field2` example plus compact semantic-minimum workflow metadata.
- `../tests/test_documentation_workflows.py` — identity, exact-example, scenario-minimum and token-aware root-option regressions.


## v0.37 empty-root and WF03 hardening artifacts

- `EMPTY_ROOT_WF03_HARDENING.md` — additive scope/decision/evidence record for the targeted runtime + documentation hardening correction.
- `../src/docengine/project.py` — fail-closed rejection of empty explicit project roots for discovery and initialization.
- `../docs/CORE_WORKFLOWS.md` — complete fresh-project A/B/C envelopes plus invalidation/sync/verify completion for WF03.
- `../tests/test_project.py` and `../tests/test_documentation_workflows.py` — empty-root runtime and root-command guard regressions.

## v0.38 empty-docs-root hardening artifacts

- `EMPTY_DOCS_ROOT_HARDENING.md` — additive scope/decision/evidence record for the pre-existing empty documentation-root inconsistency discovered during the v0.37 full-package review.
- `../src/docengine/project.py` — fail-closed rejection of empty explicit documentation roots for discovery and initialization.
- `../docs/CLEAN_CHAT_QUICKSTART.md` and `../docs/CLI_CONTRACT.md` — explicit non-empty policy for both project-root and documentation-root CLI overrides.
- `../tests/test_project.py`, `../tests/test_p1_init.py`, and `../tests/test_documentation_workflows.py` — API/CLI/no-mutation/false-verify regressions.

## v0.39 project-config root-policy sync artifacts

- `PROJECT_CONFIG_ROOT_POLICY_SYNC.md` — additive documentation-only record for synchronizing the active project-configuration reference with the accepted v0.38 explicit-root policy.
- `../docs/PROJECT_CONFIG.md` — now states that explicit string `--project-root` and `--docs-root` overrides must be non-empty/non-whitespace; empty explicit values are exit-4 usage/config errors, while explicit `--docs-root .` remains valid.
- `../tests/test_documentation_workflows.py` — regression coverage for current package identity and active project-config root-policy wording.
