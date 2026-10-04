# Repository Persistence Workflow

This document describes how to persist the final Generic Documentation Engine handoff as a long-lived Git repository without weakening release-manifest or audit guarantees.

## Bootstrap a repository

The source archive is designed to be unpacked directly into a Git worktree:

```bash
git init
git add .
git commit -m "Import Generic Documentation Engine baseline"
# Install once when build/test dependencies are available.
python -m pip install -e '.[test]'
python -m pytest -q
python tools/audit_spec.py
python tools/audit_axes.py --json
python tools/release_manifest.py validate --json
python tools/release_check.py --json
git status --porcelain
```

The final command must print nothing. Git metadata (`.git/`) and local caches are repository-local/transient state and are intentionally excluded from release inventory. Repository control files such as `.gitignore`, `.gitattributes`, `.editorconfig`, and `.github/` are normal tracked release files.

## What is canonical

- New AI/chat sessions that need to **learn or use the engine** start with `README.md` → `docs/CLEAN_CHAT_QUICKSTART.md` → the relevant `docs/CORE_WORKFLOWS.md` workflow. `START_HERE_AGENT.md` is the maintainer/release handoff for continuing engine maintenance.
- `plan/phase_records/*.json` are canonical execution/decision records.
- `OPEN_QUESTIONS_AND_AMBIGUITIES.md` is the discoverable ambiguity/deferred-boundary index.
- `MANIFEST.json` is generated release-package integrity evidence; do not hand-edit it.
- `plan/evidence/` contains retained audit evidence. Historical evidence is append-only for practical repository use: do not rewrite old evidence merely to make current tooling prettier.
- `dist/` intentionally contains exactly one active wheel and is tracked. Do not add `dist/` to `.gitignore`.

## Normal development

1. Create a branch.
2. Change source/spec/docs/tests together as required.
3. Run the CI-equivalent checks listed below.
4. If package metadata or wheel contents changed, bump the Python package version before rebuilding the active wheel. Do not publish different wheel bytes under the same version.
5. Rebuild the active wheel and remove build intermediates.
6. Regenerate `MANIFEST.json` only through `tools/release_manifest.py`.
7. Re-run manifest/spec/axis checks and confirm `git status --porcelain` contains only the intended tracked changes before commit.

## Required checks for ordinary commits / pull requests

```bash
python -m pytest -q
python tools/audit_spec.py
python tools/audit_axes.py --json
python tools/release_manifest.py validate --json
python tools/release_check.py --json
```

The GitHub `CI` workflow runs the same set and fails if the worktree becomes dirty.

## Release-only checks

Before a release/tag/handoff archive:

```bash
python tools/benchmark_release.py --json
```

Then rebuild/freeze the accepted manifest/archive using the release procedure in `docs/RELEASE_GATE.md`. The `Release gate` GitHub workflow runs this performance check on matching tags or manual dispatch.

## Version and tag policy

The repository handoff/package version and Python runtime package version are separate identities. Do not create the stable Git tag `v0.1.0` while the Python package still has a development version such as `0.1.0.dev22`.

Suitable repository tags before the stable runtime release include:

```text
handoff-v0.39.0
engine-v0.1.0.dev22
```

Reserve `v0.1.0` for a Python package whose actual version is `0.1.0`.

## Public vs private repository

The package metadata currently declares a proprietary specification prototype. This repo-ready handoff assumes a private repository unless the rights/license policy is changed explicitly. Do not infer an open-source license from the presence of source code.


## Offline / pre-provisioned environments

The repository does not vendor Python build/test dependencies. A first editable install may therefore require package-index access. In an offline environment that already provides compatible `pytest`/`jsonschema`, the source checkout can run the required checks directly because `pyproject.toml` declares `pythonpath = ["src"]`. Repository persistence acceptance is about Git/release-tree consistency, not dependency vendoring. Wheel installation remains a separate release/package check.


## Windows repository portability

The canonical files are UTF-8 and tooling must not depend on the Windows ANSI code page. `tools/audit_spec.py` reads canonical JSON/text explicitly as UTF-8.

The synthetic performance benchmark is cross-platform: POSIX uses `resource.getrusage`; Windows uses the process PeakWorkingSetSize via the standard-library `ctypes` interface. No third-party runtime dependency is introduced.

Lock semantics intentionally differ by platform in v0.1:

- POSIX: true shared-reader / exclusive-writer lock;
- Windows: safe serialization through `msvcrt`; a second concurrent reader receives the normal `runtime_busy` result rather than sharing the lock.

CI exercises the repository on Ubuntu/Python 3.11 and Windows/Python 3.14. A release must not claim Windows repository readiness from Linux-only evidence.


## Fresh-checkout byte integrity

`.gitattributes` canonicalizes repository text to LF. Release generation must therefore happen from already-canonical LF bytes. `tools/release_manifest.py generate` rejects UTF-8 text containing CR/CRLF instead of recording hashes that would change after `git add`/checkout. CI runs manifest validation immediately after `actions/checkout`, before editable installation or pytest, so Git transport/normalization defects fail at the boundary where they occur.

Equivalent Windows lexical path spellings are not distinct transaction roots. Journal paths are derived only after `Path.resolve()` confinement, preventing long-name/8.3 aliases from causing false `relative_to` failures while retaining symlink escape protection.
