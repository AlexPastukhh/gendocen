# Transaction lifecycle repair — P-1

Scope: eliminate missing-journal recovery blockers during transaction creation
and retirement, including commit, synchronous rollback and explicit recovery.
P-2 performance and unresolved ordinary-directory observations are separate.

## Contract selected before implementation

- Prepare under `hardening/transaction_preparation/txn-<uuid>`; no target writes
  are permitted there. Publish the complete initial legacy-format journal by
  same-filesystem directory rename into `hardening/transactions/txn-<uuid>`.
- Keep active journal schema/layout semantics compatible: `open` / `committed`,
  schema 1.0.0. Existing active transactions continue to recover normally.
- After durable commit or complete rollback (and recovery audit when applicable),
  publish a versioned cleanup ticket in `hardening/transaction_cleanup/`.
  The ticket pins transaction identity, outcome and the complete journal digest.
  Move the active directory into this cleanup namespace before removing files.
  Delete the ticket last, only after its payload directory is gone.
- An interrupted preparation has no document writes. A valid preparation or
  completed cleanup is disposable maintenance, reported as cleanup-only;
  read-only commands remain read-only. Mutation/recover finishes maintenance.
- Only recognized preparation contents, ticket/temp formats and flat cleanup
  payloads are disposable. Unknown names/files, symlinks, invalid tickets,
  conflicting active/cleanup payloads and invalid active journals remain blocking.
  An empty *active* directory is still corruption; never guess or discard it.
- New namespaces/ticket schema are an additive lifecycle extension. Existing
  receipt/baseline/state/history, active journals and layout marker 1.0.0 are
  not rewritten. Older runtimes can still read active journals; they do not
  perform maintenance of the new side namespaces.

## Required evidence

Inject failures before/after initial journal publication, activation, durable
commit, cleanup ticket publication, payload relocation and individual cleanup
deletions. Cover synchronous rollback and explicit recovery too. Preserve target
bytes for unactivated attempts; recover open writes; preserve committed/restored
bytes after completion. Retry recovery and ordinary commands without manual state
editing. Keep corrupt evidence/external-edit/failed-rollback protections and
legacy committed/open journal regressions. Include hard process exits across
the lifecycle, source/full-suite checks, installed-wheel checks and Windows host
verification. Report the existing Windows symlink privilege limitation honestly.

## Local implementation and acceptance

Runtime `0.1.0.dev24`, package `0.41.0-p8-transaction-lifecycle-repair` implements
the selected additive lifecycle. Commit, successful synchronous rollback and
explicit recovery share ticket publication, payload relocation and ticket-last
cleanup. Legacy active journals still parse and recover. Corrupt lifecycle
evidence is preflighted before any recovery target mutation.

- New lifecycle suite: **61 passed**, including fourteen real subprocess exits,
  original CLI failures, committed/rolled-back/recovered retirement windows,
  metadata/schema/type tampering, retry/idempotence and symlink confinement.
- Linux/Python 3.12 full source suite: **362 passed, 1 platform skip**.
- Isolated installed dev24 wheel: the same **61 lifecycle tests pass**, with no
  checkout source package available. Wheel Python files match source byte-for-byte.
- Specification/axis audits, source release lifecycle and normalized release
  benchmark pass. Build output was removed before final package auditing.
- Evidence: [pytest](evidence/TRANSACTION_LIFECYCLE/pytest.txt),
  [installed wheel](evidence/TRANSACTION_LIFECYCLE/installed_wheel_pytest.txt),
  [lifecycle](evidence/TRANSACTION_LIFECYCLE/lifecycle.json),
  [benchmark](evidence/TRANSACTION_LIFECYCLE/benchmark.json).

## Windows host application and acceptance — 2026-10-07 UTC

Applied through Tunnel App to `C:\Users\alexa\gendocen` after all 678 dev23
baseline files matched SHA256. All 686 initial dev24 release files then matched
the prepared snapshot. Existing worktree changes, branch `main` and HEAD were
preserved; no commit/push or desktop GUI interaction was performed.

- Windows/Python 3.14.7 source suite: **342 passed,
  6 skipped, 15 fixture failures**.
- The 15 failures match the previous dev23 failures by test identity
  and mechanism: `Path.symlink_to` raises `WinError 1314` before engine assertions.
  They do not establish a runtime regression and do not count as passing security
  checks. No Windows symlink privilege/settings were changed automatically.
- New lifecycle suite against the isolated installed dev24 wheel:
  **56 passed, 5 skipped**, no failures or errors.
  The five confinement cases skipped only because this execution context cannot
  create symlinks. The test copy has no `src` package; runtime import is from the
  isolated environment. All 61 cases, including symlink cases, passed on Linux.
- Specification/axis audits, source release lifecycle and installed-wheel flat
  and nested field workflows passed. Changing the fixture source produced the
  expected `check` exit 2, `sync` updated the output, and `verify` returned 0.
- Manifest checks passed before/after verification; tests left the repository
  worktree unchanged. Detailed counts, blocked/skipped identities and command
  results: [Windows host evidence](evidence/TRANSACTION_LIFECYCLE/windows_host.json).

P-1 deployment and available Windows checks are complete. The symlink privilege
limitation and remote CI platform gates remain explicit follow-up items. Earlier
P-2 performance work and U-1 unexplained directory observations remain separate.
This repair prevents the reproduced lifecycle windows; it does not guess recovery
instructions for legacy active directories whose journal is already missing.

## Later targeted Windows confinement closure

The subsequent maintained, user-approved elevated source profile passed **all
20 selected symlink security cases**, including **all five lifecycle confinement
cases**. JSON/JUnit/selection were read through ordinary Tunnel and independently
matched. Report access and short fixture-path defects are closed; see
[current workflow acceptance](SYMLINK_TEST_WORKFLOW.md) and
[accepted evidence](evidence/SYMLINK_TESTS/windows_elevated_after_fix.json).
The dev24/ordinary-context results above remain historical. Ordinary Python
privileges are unchanged; no repeated full Windows suite, elevated installed-wheel
profile or remote CI matrix is claimed. P-1 lifecycle runtime semantics are unchanged.
