# Filesystem symlink security tests

The engine's ordinary documentation/dependency workflow does not create filesystem
symlinks. These tests create real file/directory links to verify confinement,
configuration discovery and transaction recovery. They remain part of the full
test suite. Windows may reject fixture creation with `WinError 1314` when the
Python process has no symlink privilege; that is not a passing security check.

## Maintained runner

`tools/test_symlinks.py` selects the current `requires_symlink` pytest marker.
It has no fixed list of test names, expected count, release hash, user directory
or temporary Python environment. It derives the checkout from its own location
and uses the interpreter that prepares the run. The initial maintained profile
has 20 cases; each new report lists the current selection.

Use an existing test environment with the repository's test dependencies. For a
new environment, prepare it without elevation using the normal development setup:

```powershell
py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[test]'
& .\.venv\Scripts\python.exe tools/test_symlinks.py --prepare
```

For later runs, only the last command is needed. Run preparation in an ordinary
shell. It collects the profile without executing tests, creates a unique report
directory outside the checkout, and prints two PowerShell commands:

1. `Start-Process ... -Verb RunAs -Wait` runs this test Python with elevation.
   Approve the Windows UAC prompt manually. The runner does not initiate GUI
   interaction or change Windows policies, Developer Mode or account privileges.
2. `Get-Content -Raw ...\result.json` reads the saved result from the ordinary
   shell after the elevated window closes. Elevation applies to the test process
   and its children; it does not require elevating Tunnel or another application.

The report files are pre-created by the ordinary process and overwritten in
place. This retains their access permissions when the elevated process writes.
The runner avoids a new elevated `tempfile.mkdtemp()` report directory: on the
target host such a directory prevented the ordinary Tunnel process from reading
the first ad hoc run. Test-specific temporary directories may still use secure
defaults; their content is not needed to read the report.

Fixture storage is separate from report storage. Preparation creates a short
`gdXXXXXXXX` directory under the system temporary directory and records it as
`temporary_directory` in both JSON reports. Pytest uses its `p` child; Python's
`TEMP`/`TMP`/`TMPDIR` apply only to this process and its children. Deep report
paths previously caused Windows `WinError 3` during fixture copies and journal
creation. This separation avoids changing Windows long-path policies or weakening
tests. If the system temporary parent itself is unusually long, select an existing
short writable parent with `--prepare --temp-root PARENT`; both temporary storage
and reports must be outside the checkout. Old preparations without the separate
directory require preparing again. Test files remain available at that recorded
path for diagnosis and may be removed after reviewing the result.

The printed report directory contains:

- `prepared.json`: current checkout input hashes, interpreter and selected cases;
- `selected.json`: actual collected node IDs;
- `collect.stdout.txt` / `collect.stderr.txt`: preparation diagnostics;
- `pytest.stdout.txt` / `pytest.stderr.txt`: execution diagnostics;
- `junit.xml`: machine-readable test outcomes;
- `result.json`: completion, counts, capabilities, input stability and verdict.

`ok: true` for **preparation** only proves successful collection. For an actual
run, require `collection_only: false`, `complete: true`, `ok: true`, and all
selected cases passing with zero failures, errors or skips. The runner probes
both file and directory link creation first; missing capability cannot turn into
a passing profile. Console closure alone proves no test result.

Keep checkout inputs stable between preparation and execution and while tests
run. If source/tests/docs change, prepare again; a prepared directory executes
once and retains its result. The runner accepts current dirty development files
and does not require them to match an old release manifest, but captures current
eligible checkout bytes and rejects changes across the run. It never resets,
commits or pushes the worktree. Reports must remain outside the checkout.

On a POSIX environment with symlink support, `python tools/test_symlinks.py
--prepare` prints an ordinary `--run DIRECTORY` command instead of requesting
elevation. If symlinks already work for an ordinary Windows Python process, the
same `--run DIRECTORY` command can be used without elevation.

## Adding or changing tests

Mark each test that requires creating real symlinks:

```python
import pytest

@pytest.mark.requires_symlink
def test_new_link_confinement(tmp_path):
    ...
```

Parameterized cases are included automatically. Mark consuming tests when a
shared helper/fixture creates links; the runner does not infer arbitrary Python
call graphs. `tests/test_symlink_profile_contract.py` catches omitted markers on
test functions containing direct `.symlink_to()` / `.symlink()` calls. It runs
in the ordinary full CI suite. The marker is registered in `pyproject.toml`.

After additions, prepare again and inspect `selected.json`/`selected_count`.
Do not maintain a parallel list in the runner or derive future selection from
historical failed-test evidence. Full CI already includes the marked cases;
this profile is an additional targeted run, not a replacement for full CI.

## Evidence and current limits

Retain checked reports under `plan/evidence/SYMLINK_TESTS/` when recording
acceptance; keep raw temporary logs outside the release checkout until reviewed.
The first protected ad hoc report was exported by a user-approved elevated
process into ordinary-precreated files. It recorded 17 passed / 3 failed. The
first maintained elevated run had 14 passed / 1 failed / 5 setup errors. Both
had symlink capability and stable checkout inputs; neither is a passing gate.
Long temporary paths reproduced failed fixture copies, while a short path
successfully copied fixtures and prepared transaction cleanup. The runner now
separates short fixture storage from retained reports. The subsequent actual
elevated Windows run passed **all 20 selected cases**, with zero failures, errors
or skips and unchanged checkout inputs. Its result/JUnit/selection were read back
through ordinary Tunnel and independently matched. This closes report access and
short-path correction acceptance, including the previously failing P7 migration
and all five lifecycle cases. See [accepted Windows result](../plan/evidence/SYMLINK_TESTS/windows_elevated_after_fix.json),
[JUnit](../plan/evidence/SYMLINK_TESTS/windows_elevated_after_fix.junit.xml) and
[selection](../plan/evidence/SYMLINK_TESTS/windows_elevated_after_fix.selected.json).
Historical failed runs remain preserved; this targeted acceptance does not claim
a repeated full Windows suite or remote CI matrix. Ordinary Python privilege is
unchanged. Historical unprivileged `WinError 1314` results remain under
`plan/evidence/COMMAND_SNAPSHOTS/windows_host.json`.
