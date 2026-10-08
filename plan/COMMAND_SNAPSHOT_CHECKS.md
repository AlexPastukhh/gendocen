# Command snapshot checks — P-2

Runtime `0.1.0.dev25`, package `0.42.0-p8-command-snapshot-checks`.
Scope: remove repeated source reads/full guards within a CLI command while
retaining actual-byte/source-code validation and transactional failure handling.
P-1 lifecycle behavior, field ownership, default recursion depth and persisted
receipt/state/layout/machine schema versions are unchanged.

## Selected behavior

- CLI evaluation and verification use a command-scoped pinned snapshot. A plain
  Markdown source supplies text and version from one byte read; managed objects
  and physical hashes are captured together by catalog scan. Exact field versions
  use the pinned object and preserve existing canonical hash semantics.
- Repeated reads reuse captured values/versions; successful derived targets run
  once per operation. Record/render steps use cheap failure checkpoints instead
  of traversing all accumulated inputs again.
- Source bytes, descriptor ownership, registry identity and project Python are
  checked at final completion. This happens inside the CLI lock/transaction;
  mismatches roll back engine-managed output/evidence. Verification reports a
  blocking finding. An explicitly observed error stays failed after restoration.
- Keep canonical inputs/code stable during a command. A temporary unobserved edit
  that is fully restored before validation need not be detected; captured values
  stay stable throughout that command. External source edits are not rolled back.
- Default library `BuildOperation` remains strict (`validation="per_call"`).
  Explicit command mode requires caller finalization via `assert_current()` and
  appropriate publication guards. Custom stores retain per-read version behavior
  unless they supply the catalog snapshot capability. No persistent cache/watcher,
  helper integration, manual file-selection requirement or schema migration.

## Acceptance

`tests/test_command_snapshots.py` covers 16/64/128 independent Markdown pairs with
exactly one capture plus one final source-byte validation and a single full
command guard; exact CRLF/text/hash and raw-pointer versions; delete/same-size
same-mtime/source/code changes; stable snapshot reuse and explicit sticky errors;
custom-store behavior; descriptor validation; warmed sync rollback/retry;
read-only verification; and 16/64/128 computed fields sharing one raw source.
Existing operation, flat/nested field, materialization, protocol and lifecycle
regressions remain required. Source/full-suite, isolated wheel, audits, release
lifecycle and Windows checks must be recorded before delivery.

`tools/benchmark_command_snapshots.py --json` checks source-I/O bounds and reports
three timing samples for 16/64/128 goals. Its success criterion is deterministic
work/status counts, not a fixed wall-clock SLA. The original P-2 independent-pair
check made `4*N*N + 12*N` version calls; current-byte validation must remain while
the repeated accumulated-source sweeps are removed.

## Local acceptance

- New snapshot regressions: **19 passed**.
- Linux/Python 3.12.14 full source suite: **381 passed, 1 platform skip**.
- Isolated installed dev25 wheel: **86 passed**, covering command snapshots,
  existing library/CLI operation behavior and all 61 P-1 lifecycle cases. The
  test copy has no checkout source package; runtime import/version were checked.
  Wheel Python bytes match source exactly.
- Specification/axis audits, release lifecycle and normalized release benchmark
  pass. Existing state/machine/layout versions are unchanged.

| Independent pairs | Median check seconds | Source-byte reads | Full validations |
| ---: | ---: | ---: | ---: |
| 16 | 0.019762 | 64 | 1 |
| 64 | 0.051908 | 256 | 1 |
| 128 | 0.100538 | 512 | 1 |

Each pair has two distinct canonical files. Source reads are exactly `4*N`,
including the final validation: two reads per used file. The installed-wheel
benchmark confirms the same counts. These are three-sample local timing medians
for this corpus, not a project-wide or Windows latency SLA.

Evidence: [source tests](evidence/COMMAND_SNAPSHOTS/pytest.txt),
[wheel tests](evidence/COMMAND_SNAPSHOTS/installed_wheel_pytest.txt),
[source benchmark](evidence/COMMAND_SNAPSHOTS/benchmark.json),
[wheel benchmark](evidence/COMMAND_SNAPSHOTS/installed_wheel_benchmark.json),
[lifecycle](evidence/COMMAND_SNAPSHOTS/lifecycle.json),
[release benchmark](evidence/COMMAND_SNAPSHOTS/release_benchmark.json).

## Windows host application and acceptance — 2026-10-07 UTC

Applied through Tunnel App to `C:\Users\alexa\gendocen` after all **687** dev24
baseline file hashes matched. All **696** initial dev25 files then matched the
prepared snapshot. Existing worktree changes, branch `main` and HEAD were
preserved; no commit/push or desktop GUI interaction was performed.

- Windows/Python 3.14.7 source suite: **361 passed,
  6 skipped, 15 fixture failures**. All 19 new snapshot tests passed.
- The 15 failures match the preceding dev24/dev23 failures by identity
  and mechanism: `Path.symlink_to` raises `WinError 1314` before engine assertions.
  They are blocked security checks, not passing tests. No symlink privilege or
  Windows settings were changed automatically.
- Isolated installed dev25 wheel, snapshot/operation/P-1 lifecycle profile:
  **81 passed, 5 skipped**, no failures/errors.
  Five lifecycle confinement cases skip only for the missing symlink privilege;
  all 86 cases passed on Linux. The installed test copy has no checkout `src`;
  runtime import/version were asserted in the isolated environment.
- Source/installed snapshot benchmarks satisfy the exact `4*N` source-read bound
  and one final full validation per command. Three-sample medians on this host:

| Independent pairs | Source seconds | Wheel seconds | Source-byte reads | Full validations |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 0.208896 | 0.189234 | 64 | 1 |
| 64 | 0.536222 | 0.504355 | 256 | 1 |
| 128 | 1.149950 | 1.087010 | 512 | 1 |

These are measured timings for this corpus, not a universal latency SLA.
Specification/axis audits, release lifecycle, normalized release benchmark and
installed-wheel flat/nested field updates passed. A source change gave `check`
exit 2, then `sync` updated the expected output and `verify` returned 0.
Manifest checks passed before/after verification; repository worktree state did
not change during tests. Counts, blocked/skipped identities and benchmark samples:
[Windows host evidence](evidence/COMMAND_SNAPSHOTS/windows_host.json).

P-2 application and available Windows checks are complete. The symlink privilege
limitation and unexecuted remote CI gates remain explicit follow-up items.

## Later targeted Windows security closure

The subsequent maintained, user-approved elevated source profile passed **all
20 selected symlink security cases**, including the five lifecycle cases that
were blocked in the ordinary context. JSON/JUnit/selection were read through
ordinary Tunnel and independently matched. Report access and short fixture-path
defects are closed; see [current workflow acceptance](SYMLINK_TEST_WORKFLOW.md)
and [accepted evidence](evidence/SYMLINK_TESTS/windows_elevated_after_fix.json).
The results above remain historical. Ordinary Python privileges are unchanged;
this follow-up does not claim a repeated full Windows suite, elevated installed
wheel profile or remote CI matrix. Command snapshot semantics/runtime are unchanged.
