# START HERE — engine maintainer / release handoff

This checkout preserves **P8 accepted** and the additive post-acceptance correction chain through **v0.39 project-config root-policy sync** (v0.25–v0.39), then adds **v0.40 field dependency expansion**. Then **v0.41 transaction lifecycle repair** closes the prepared-journal/cleanup interruption windows. Then **v0.42 command snapshots** remove repeated source I/O while retaining final validation. Runtime build: **0.1.0.dev25**. No implementation phase follows P8.

Additive work in this checkout: v0.40 implements [`plan/FIELD_DEPENDENCY_EXPANSION.md`](plan/FIELD_DEPENDENCY_EXPANSION.md), following the flat `FIELD-AUTHORING-1` helper. It adds nested fields, P-2 error handling and operation-scoped reuse. Expansion acceptance is recorded separately from historical P0–P8 evidence.

The additive [Markdown-field example](examples/markdown_field_project/README.md)
demonstrates author-selected slices from tracked canonical prose with the same
helper/runtime. Its checks and scope are recorded in
[`plan/MARKDOWN_FIELD_EXAMPLE.md`](plan/MARKDOWN_FIELD_EXAMPLE.md); no runtime,
wheel or persisted-schema version changes accompany this example.

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

For Windows link-fixture privilege failures, use the maintained
[`tools/test_symlinks.py`](tools/test_symlinks.py) profile described in
[`docs/SYMLINK_TESTS.md`](docs/SYMLINK_TESTS.md). Preparation runs without elevation
and prints manual execution/readback commands. Future real-link tests require
the `requires_symlink` marker; full CI checks direct creators for missing markers.
Never infer a passing security gate from a closed console or skipped cases.

The maintained targeted Windows profile is now verified: **20 selected / 20
passed**, zero failures/errors/skips, including all five lifecycle confinement
cases. Ordinary report readback and short independent fixture storage are also
confirmed. Current acceptance/evidence is in
[`plan/SYMLINK_TEST_WORKFLOW.md`](plan/SYMLINK_TEST_WORKFLOW.md). Older P-1/P-2
Windows counts remain historical; ordinary Python privileges are unchanged and
the full Windows/remote CI matrix was not rerun by this targeted follow-up.
