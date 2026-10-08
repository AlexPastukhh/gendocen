# P8 Release Gate

P8 is the final v0.1 consolidation phase. It does not change project semantic authority; it proves that the already-implemented runtime, persisted evidence, release package and handoff agree.

## Release tools

```bash
python tools/release_check.py --json
python tools/benchmark_release.py --json
python tools/release_manifest.py validate --json
python tools/audit_axes.py --json
python tools/audit_spec.py
```

`benchmark_release.py` is self-contained for the source archive: it injects the repository `src/` directory into its benchmark subprocess environment, so callers do **not** need to set `PYTHONPATH`.

`release_check.py` runs bundled lifecycle checks only on temporary copies. `sample_project` intentionally remains an onboarding fixture with initial semantic review outstanding; release readiness is proven by completing the explicit review lifecycle on a clean temporary copy.

## Windows filesystem-link test profile

For the maintained symlink security profile and localized elevated test process,
follow [Filesystem symlink tests](SYMLINK_TESTS.md). Run
`python tools/test_symlinks.py --prepare` in an ordinary test environment, then
use its printed execution/readback commands. Require the actual run's retained
JSON/JUnit result; successful collection, console closure, `WinError 1314` or
skipped link cases do not close the security check. Full CI still includes every
marked case. New link tests use `@pytest.mark.requires_symlink`; the full-suite
marker contract catches unmarked direct creators.

## Performance budget

The blocking budget is `spec/release/PERFORMANCE_BUDGET.json`. It was established before the final P8 release rerun. CPU time is normalized by a deterministic same-interpreter calibration and combined with an independent RSS ceiling plus exact workload/correctness counts.

P8 acceptance requires every check in `plan/evidence/P8/performance_gate.json` to pass. This closes DAX18, which was intentionally partial in P7.

## Manifest

`MANIFEST.json` is engine-package integrity evidence, not project runtime state. It tracks source/spec/docs/examples/tests/tools, repository control files and the active wheel, excluding itself, `.git/`, and transient cache/build/development artifacts.

Generate only through:

```bash
python tools/release_manifest.py generate \
  --version 0.42.0-p8-command-snapshot-checks \
  --runtime 0.1.0.dev25 \
  --phase P8 \
  --status accepted
```

Validate through `release_manifest.py validate` and `tools/audit_spec.py`.

## Axis closure

`tools/audit_axes.py` derives the final release closure from canonical `plan/phase_records/*.json`. It requires all registry release-gate axes plus promoted DAX18 to be `pass` in P8, all P8 criteria to pass, and every prior phase to remain accepted without unresolved blocking questions.

DAX14 and DAX16 are non-gating in the axis registry but remain documented in `plan/P8_FINAL_AXIS_AUDIT.md` because P7 post-axis work established their final diagnostics/migration evidence.


## Repository persistence

For a long-lived Git checkout, follow `REPOSITORY_WORKFLOW.md`. Git internals are intentionally excluded from release inventory, while `.github/`, `.gitignore`, `.gitattributes` and `.editorconfig` are tracked release files. A repository-ready handoff must additionally prove that initializing and using Git does not break audits/manifest validation and does not leave ordinary test/install artifacts visible in `git status`.


## Fresh-checkout gate

Repository release integrity is checked on the exact Git checkout bytes before dependency installation or tests. Git-normalized UTF-8 text must already use LF; `tools/release_manifest.py generate` refuses CR/CRLF text instead of freezing a manifest that Git would later rewrite. Transaction path identity is also regression-tested against lexically different paths that resolve to the same documentation root, modeling Windows 8.3/long-name aliasing.
