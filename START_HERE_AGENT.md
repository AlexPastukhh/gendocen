# START HERE — AI / new chat handoff

This archive is canonical through **P8 accepted**, the **v0.25 post-axis consistency correction**, the **v0.26 Git-persistence correction**, and the **v0.27 Windows repository-portability final correction**. Runtime build: **0.1.0.dev19**. No implementation phase follows P8.

## Read first

1. `OPEN_QUESTIONS_AND_AMBIGUITIES.md`
2. `docs/RELEASE_GATE.md`
3. `docs/PHASE_ACCEPTANCE_MODEL.md`
4. `docs/REPOSITORY_WORKFLOW.md`
5. `plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md`
6. `plan/REPOSITORY_PERSISTENCE_AUDIT.md`
7. `plan/P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md`
8. `plan/P8_FINAL_AXIS_AUDIT.md`
9. `plan/phase_records/P8_EXECUTION_RECORD.json`

## Final invariants

- Markdown-first and explicit structured ownership remain unchanged.
- Semantic verdicts remain explicit human/AI actions; release verify never invents them.
- `verify` is project-level/read-only; engine release integrity uses release tools.
- machine envelope schema is 2.0.0; exit codes remain 0/2/3/4/5.
- runtime layout is 1.0.0 with P7 transactional recovery/migration hardening.
- DAX18 is PASS in P8; historical P7 partial is represented by resolved `P7-CG1`, not retroactively rewritten.
- POSIX supports shared readers; Windows v0.1 safely serializes readers and does not guarantee concurrent-reader parity.
- canonical audit/spec text is UTF-8 independent of host locale.
- synthetic benchmark peak RSS is measured portably on POSIX and Windows.
- path-like evidence refs in canonical phase records resolve inside the release tree.
- global release closure is derived by `tools/audit_axes.py`; open carried gates block final release.
- `.git/` and local development caches are never release-manifest content; repository control files are tracked.
- `dist/` intentionally tracks exactly one active wheel and must not be globally ignored.
- CI includes Ubuntu/Python 3.11 and Windows/Python 3.14 repository checks.

## Required checks

```bash
python -m pytest -q
python tools/release_check.py --json
python tools/benchmark_release.py --json
python tools/audit_axes.py --json
python tools/audit_spec.py
python tools/release_manifest.py validate --json
```

No caller `PYTHONPATH` setup is required.
