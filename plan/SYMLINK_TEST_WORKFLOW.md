# Maintained filesystem-link test workflow

Scope: retain the targeted Windows test runner in the checkout, make its purpose
discoverable and include future real-link cases without a historical failure list.
Runtime remains `0.1.0.dev25`; source package code, wheel and dependency semantics
are unchanged. This is test/support/documentation maintenance.

## Implementation

- `tools/test_symlinks.py`: ordinary preparation/collection, optional manually
  elevated execution, external retained JSON/JUnit/logs and strict all-pass verdict.
- `pyproject.toml`: registered `requires_symlink` marker. All 16 existing creator
  functions, including five parameterized lifecycle cases, are marked (20 cases).
- `tests/test_symlink_profile_contract.py`: full CI detects unmarked direct link
  creators. Helpers/fixtures require marking consuming tests explicitly.
- `docs/SYMLINK_TESTS.md`, release/workflow/agent/file-map links: future chats and
  maintainers can find setup, launch, result reading and adding tests.

The first ad hoc elevated runner used `tempfile.mkdtemp()` for reports. Windows
created a directory unreadable by the ordinary Tunnel process. Its console
closed after execution. A subsequent user-approved process exported the report
into ordinary-precreated files: it recorded 17 passed / 3 failed, not a pass.
The maintained workflow pre-creates report files without elevation and
writes them in place. Source/test/fixture input hashes are captured from the
current checkout, not a hardcoded release; changes require fresh preparation.
Test temporary storage is explicitly external. It now uses a short independent
`gdXXXXXXXX` directory, with pytest `--basetemp` set to its `p` child. Report
depth therefore does not lengthen fixture or transaction-journal paths; no Windows
policy changes are required. `--temp-root` supports a short writable parent when
the native temporary parent is unusually long.
An executed directory cannot overwrite its previous result on repeated invocation.

## Local acceptance

- Complete Linux/Python 3.12 source suite: **383 passed, 1 platform skip** after the short-path regression was added.
- Maintained runner: **20 selected, 20 passed**, zero skips/failures/errors;
  eligible checkout bytes unchanged. After removal of owned setup transients,
  all seven audit-hygiene/marker/regression cases and spec/axis/manifest audits pass.
- Independent minimal future-test fixture: two new marked parameter cases were
  discovered/executed without changing the runner; an unmarked creator was
  excluded from the profile and rejected by the full-suite marker guard.
- Repeated execution was rejected and the previous JSON verdict remained intact.
- Initial setup attempts found pending-manifest audit failures and local temporary
  files falling back into the workspace copy. The manifest was regenerated and
  owned transients moved outside the checkout; final checks used explicit external
  temporary storage. These were setup issues, not claimed runtime regressions.

Evidence: [local profile](evidence/SYMLINK_TESTS/local_profile.json),
[local acceptance](evidence/SYMLINK_TESTS/local_acceptance.json).

## Windows application and available support checks

Applied to `C:\Users\alexa\gendocen` after all 697 dev25 baseline hashes matched;
703 initial maintenance files then matched. Branch/HEAD and existing worktree
changes were preserved; no commit/push, OS policy changes or desktop automation.

- Marker contract: **1 passed** on Windows/Python 3.14.7.
- Maintained preparation: **20 collected**, no test execution, report readable
  from ordinary Tunnel.
- Ordinary execution was correctly blocked with **WinError 1314 / exit 4**;
  `ok: false` and `complete: false` remained explicit. The saved JSON was readable
  from the ordinary process; missing capability did not become passing/skipped
  acceptance. No full Windows suite was repeated for these test-only changes.
- Manifest/spec/axis audits passed; verification left repository status unchanged.

[Windows support evidence](evidence/SYMLINK_TESTS/windows_support.json).
The user-approved maintained elevated run was readable from ordinary Tunnel,
confirming report access after elevated writes. It recorded **14 passed / 1 failed /
5 setup errors**. Deep Windows temporary paths caused fixture-copy failures; an
independent ordinary-process probe reproduced failed long copies and successful
short copies plus cleanup-ticket preparation. A regression test now exercises
fixture copies and long journal names with deep report storage. Both initial
failed runs are retained in [Windows elevated evidence](evidence/SYMLINK_TESTS/windows_elevated_before_fix.json).

## Final Windows acceptance

The subsequent user-approved elevated Windows/Python 3.14.7 run passed **20 of 20**
selected cases, with **zero failures, errors or skips**. The saved JSON, JUnit and
node selection were read through ordinary Tunnel and independently matched. Both
file/directory symlink capability and unchanged repository inputs are confirmed.
The P7 migration symlink/corrupt receipt case and all five lifecycle cases passed;
report readback and short temporary storage acceptance are closed.

The ordinary corrected support/lifecycle/P7 selection also passed **78 cases**,
with one documented POSIX-only shared-reader skip. Manifest/spec/axis audits pass.
No full Windows suite or remote CI matrix was rerun; ordinary symlink privileges
and OS policies remain unchanged. No runtime source or wheel change is involved.

Evidence: [result](evidence/SYMLINK_TESTS/windows_elevated_after_fix.json),
[JUnit](evidence/SYMLINK_TESTS/windows_elevated_after_fix.junit.xml),
[selected nodes](evidence/SYMLINK_TESTS/windows_elevated_after_fix.selected.json).
Historical failed reports remain alongside the accepted result.
