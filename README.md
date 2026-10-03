# Generic Documentation Engine — specification/runtime package v0.28 — Git-checkout portability candidate

Target stable runtime: **v0.1**. Current engine build: **0.1.0.dev20**.

P0–P8 remain complete. v0.28 preserves the accepted engine semantics and corrects two repository-checkout defects discovered only after the first real GitHub push: manifest evidence could be frozen with CRLF bytes before Git normalized the committed blob to LF, and transaction journal path serialization mixed canonical confinement paths with lexical Windows path spellings such as 8.3 aliases. The correction makes manifest freezing reject non-canonical CR/CRLF UTF-8 text, serializes transaction paths from canonical resolved identities, and validates the fresh checkout manifest before CI installs or runs tests.

## Operational CLI

```text
init status check diff explain sync rebuild validate materialize verify history graph resources recover migrate
```

## Final release tooling

```bash
python tools/release_check.py --json
python tools/benchmark_release.py --json
python tools/release_manifest.py validate --json
python tools/audit_axes.py --json
python tools/audit_spec.py
```

No external `PYTHONPATH` setup is required for the benchmark command.

## Start here

1. `START_HERE_AGENT.md`
2. `OPEN_QUESTIONS_AND_AMBIGUITIES.md`
3. `docs/RELEASE_GATE.md`
4. `docs/PHASE_ACCEPTANCE_MODEL.md`
5. `docs/REPOSITORY_WORKFLOW.md`
6. `plan/GITHUB_CHECKOUT_PORTABILITY_AUDIT.md`
7. `plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md`
8. `plan/REPOSITORY_PERSISTENCE_AUDIT.md`
9. `plan/P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md`
10. `plan/P8_FINAL_AXIS_AUDIT.md`
11. `plan/phase_records/P8_EXECUTION_RECORD.json`

## Package identity

- specification/runtime package: `0.28.0-p8-git-checkout-portability-candidate`;
- runtime build: `0.1.0.dev20`;
- target stable runtime: `0.1.0`;
- persisted-state schema: `1.0.0`;
- machine-output schema: `2.0.0`;
- runtime-layout schema: `1.0.0`;
- current engine phase: `P8 accepted`; repository portability correction: `candidate — local gates pass; GitHub Ubuntu/Windows fresh-checkout CI pending`;
- next engine phase: none — v0.28 is a repository/handoff portability correction, not P9.

## Git persistence

The archive is intended to be unpacked directly into a private Git repository. Read `docs/REPOSITORY_WORKFLOW.md` before the first commit. `.git/` and local caches are excluded from release inventory; `.github/`, `.gitignore`, `.gitattributes`, `.editorconfig`, historical evidence and the single active wheel remain tracked.

The supported repository regression surface is exercised on Ubuntu/Python 3.11 and Windows/Python 3.14 in CI. Real Windows acceptance evidence for dev19 is retained in `plan/evidence/windows_portability/windows_real_host_gate_full.txt`. POSIX readers may share the runtime lock; Windows v0.1 intentionally serializes readers safely and reports `runtime_busy` to a concurrent second reader.

Fresh checkout integrity is now a first-class release invariant. Git-normalized UTF-8 text must already use LF before manifest generation, and CI validates `MANIFEST.json` immediately after checkout. Transaction journals derive relative paths only from canonical resolved path identities, while existing symlink/path-confinement checks remain in force.
