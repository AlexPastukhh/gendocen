# START HERE — engine maintainer / release handoff

This archive is canonical through **P8 accepted** and the additive post-acceptance correction chain through **v0.39 project-config root-policy sync** (v0.25–v0.39). Runtime build: **0.1.0.dev22**. No implementation phase follows P8.

> This file is the maintainer/release handoff. To learn or use the engine for project authoring, start with `README.md` → `docs/CLEAN_CHAT_QUICKSTART.md` → the relevant `docs/CORE_WORKFLOWS.md` workflow. Do not use this maintainer path as the default project-authoring tutorial.

## Read first

1. `OPEN_QUESTIONS_AND_AMBIGUITIES.md`
2. `docs/RELEASE_GATE.md`
3. `docs/PHASE_ACCEPTANCE_MODEL.md`
4. `docs/REPOSITORY_WORKFLOW.md`
5. `plan/GITHUB_CHECKOUT_PORTABILITY_AUDIT.md`
6. `plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md`
7. `plan/REPOSITORY_PERSISTENCE_AUDIT.md`
8. `plan/P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md`
9. `plan/P8_FINAL_AXIS_AUDIT.md`
10. `plan/phase_records/P8_EXECUTION_RECORD.json`

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
- manifest generation refuses CR/CRLF in Git-normalized UTF-8 text; fresh checkout validation runs before install/test.
- transaction journal relative paths are derived from canonical resolved identities, so equivalent Windows long/8.3 path spellings cannot create false escapes.

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
