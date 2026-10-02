# Repository Persistence Audit — v0.26 repo-ready handoff

> Historical v0.26 audit. A real Windows/Python 3.14 checkout later exposed locale/benchmark/test portability defects. Cross-platform repository readiness is superseded by `WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md` and v0.27; the Git metadata/cache findings and corrections recorded here remain valid.

Date: 2026-10-03
Status: **PASS — repository persistence gate completed**
Runtime distribution: **0.1.0.dev18**
Specification/runtime package: **0.26.0-p8-repo-ready-final**

## Scope

This is not a new engine implementation phase. P0–P8 remain accepted. v0.26 hardens the final v0.25 handoff for long-lived Git persistence and clean transfer to future AI/chat sessions.

## Confirmed v0.25 repository defects

1. `.git/` was not excluded from release inventory. A plain `git init` caused `audit_spec.py`/manifest parity to treat Git internals as package files.
2. No `.gitignore` existed, so tests/install left normal Python caches/build metadata visible as untracked Git changes.
3. Repository normalization/control files and CI workflows were absent.
4. There was no canonical repository-maintenance runbook explaining historical evidence, active `dist/`, manifest regeneration, version/tag policy, or private/proprietary assumption.
5. Git persistence itself was not covered by an acceptance gate.

## Corrections

- `tools/release_manifest.py` and `tools/audit_spec.py` exclude `.git/` and matching local transient development directories while still tracking repository control files.
- `.gitignore`, `.gitattributes`, `.editorconfig` added.
- GitHub CI workflow added for tests/spec/axes/manifest/lifecycle plus clean-worktree assertion.
- Separate release-gate workflow added for the normalized performance benchmark and full release checks.
- `docs/REPOSITORY_WORKFLOW.md` defines bootstrap, canonical files, historical evidence policy, active wheel handling, release workflow and version/tag rules.
- Regression tests assert `.git` exclusion and repository-control-file tracking.
- Final acceptance requires an actual temporary Git repository: initialize, commit the release tree, run required checks, and confirm `git status --porcelain` is empty.

## Deliberate boundary

The package metadata remains proprietary. v0.26 assumes a private repository unless the owner explicitly chooses a public/open-source licensing policy. No license is inferred or changed by this persistence patch.

## Acceptance gate

PASS requires:

- full test suite;
- `tools/audit_spec.py`;
- `tools/audit_axes.py --json`;
- `tools/release_manifest.py validate --json`;
- `tools/release_check.py --json`;
- documented `tools/benchmark_release.py --json` release command;
- clean-venv wheel/source parity;
- literal `git init -> add/commit -> required checks -> git status clean` proof;
- manifest-only portable-copy repeat;
- exact ZIP member set + CRC.


## Observed acceptance evidence

- candidate full source suite: **230 passed, 253 subtests passed**;
- `SPEC AUDIT OK`;
- global axis audit: zero findings;
- release manifest validator: clean;
- bundled release lifecycle: PASS;
- literal temporary Git repository: init/add/commit + full source checks succeeded;
- `git status --porcelain` after checks: empty;
- final accepted-state wheel/manifest/portable/ZIP gates are repeated after this report is frozen.


## Final distribution evidence

- active wheel: `generic_documentation_engine-0.1.0.dev18-py3-none-any.whl`;
- wheel SHA-256: `a1c270b499b4dd0ebae0f437afea1b4bf73192c6149fa77314a8a78f3cfb493d`;
- clean-venv no-index/no-deps install: PASS;
- `pip check`: PASS;
- installed `docengine --version`: `0.1.0.dev18`;
- installed product fixture `verify`: PASS;
- wheel/source parity: **20 / 20 runtime modules identical**;
- Git bootstrap evidence: `plan/evidence/repository_persistence/`.
