# Generic Documentation Engine — specification/runtime package v0.27 — Windows repo-ready final

Target stable runtime: **v0.1**. Current engine build: **0.1.0.dev19**.

P0–P8 remain complete. v0.27 preserves the accepted engine semantics and corrects repository portability discovered by a real Windows/Python 3.14 checkout: canonical audit text is read explicitly as UTF-8, the synthetic benchmark has portable peak-RSS collection instead of a Unix-only `resource` import, the Windows lock regression matches the accepted safe-serialization contract, and CI now exercises both Ubuntu and Windows.

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
6. `plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md`
7. `plan/REPOSITORY_PERSISTENCE_AUDIT.md`
8. `plan/P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md`
9. `plan/P8_FINAL_AXIS_AUDIT.md`
10. `plan/phase_records/P8_EXECUTION_RECORD.json`

## Package identity

- specification/runtime package: `0.27.0-p8-windows-repo-ready-final`;
- runtime build: `0.1.0.dev19`;
- target stable runtime: `0.1.0`;
- persisted-state schema: `1.0.0`;
- machine-output schema: `2.0.0`;
- runtime-layout schema: `1.0.0`;
- current engine phase: `P8 accepted`; repository portability correction: `final — real Windows/Python 3.14 gate passed`;
- next engine phase: none — v0.27 is a repository/handoff portability correction, not P9.

## Git persistence

The archive is intended to be unpacked directly into a private Git repository. Read `docs/REPOSITORY_WORKFLOW.md` before the first commit. `.git/` and local caches are excluded from release inventory; `.github/`, `.gitignore`, `.gitattributes`, `.editorconfig`, historical evidence and the single active wheel remain tracked.

The supported repository regression surface is exercised on Ubuntu/Python 3.11 and Windows/Python 3.14 in CI. Real Windows acceptance evidence for dev19 is retained in `plan/evidence/windows_portability/windows_real_host_gate_full.txt`. POSIX readers may share the runtime lock; Windows v0.1 intentionally serializes readers safely and reports `runtime_busy` to a concurrent second reader.
