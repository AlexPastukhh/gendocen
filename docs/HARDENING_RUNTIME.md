# P7 Hardening Runtime

## Scope

P7 hardens the file-based documentation runtime without changing the accepted P0–P6 domain semantics. The canonical command workflow remains explicit CLI execution.

P7 adds:

- one external OS lock per documentation root;
- shared-reader / exclusive-writer command coordination;
- write-ahead rollback journals for multi-file mutations;
- explicit crash recovery with audit events;
- runtime-layout migration markers and migration registry;
- synthetic scalability baselines;
- no mandatory daemon/watch mode.

## Locking model

Official `docengine` commands use a lock keyed by the resolved documentation root. The lock file lives in the operating-system temporary directory, not inside the project, so read-only commands do not create project files merely to coordinate access.

- `status`, `diff`, `explain`, `history`, `graph`, `resources`, `verify` acquire a shared lock.
- `check`, `sync`, `rebuild`, `validate`, `materialize`, `migrate`, `recover` acquire an exclusive lock.
- multiple readers may coexist;
- a writer conflicts with readers/writers and returns a machine-readable `runtime_busy` domain failure rather than observing/creating a partial commit.

Low-level store classes are implementation primitives, not a separate concurrent-write API. Embedders that bypass the official command/orchestration surface must hold `HardeningManager` themselves.

## Transaction model

Every ordinary runtime mutation runs inside `FileTransaction` while the exclusive lock is held.

Before a file is changed, the transaction durably records:

- documentation-root-relative path;
- whether the file existed;
- SHA-256 of the pre-image;
- a fsynced backup when the file existed;
- known/planned transaction output hashes.

Only after this journal/pre-image is durable does the file change occur. Ordinary file changes still use atomic same-directory replacement.

A successful command marks the journal `committed` and removes it before the lock is released. An exception rolls the transaction back synchronously. If that synchronous rollback itself fails, P7 **preserves the transaction journal and pre-images**; it never deletes the only recovery evidence while the target may still contain transactional bytes.

## Crash recovery

A process crash can leave an `open` journal under:

```text
docs/_dependency/hardening/transactions/
```

Transaction entries are parsed strictly before any rollback action. Unknown files/symlinks, invalid transaction IDs, journal/directory ID mismatches, non-canonical paths, incoherent `existed/backup/before_hash` combinations or invalid hashes are **corruption**, never recovery instructions. Corrupt evidence blocks mutation/recovery until it is resolved; the engine does not guess or silently discard it.

Read-only commands other than `verify` refuse to inspect a potentially partial runtime and return `recovery_required`. `verify` remains a complete-report command and reports the pending transaction as a blocking finding.

Recovery:

```bash
docengine recover --json
```

Restores all pre-images/removes files created by the interrupted transaction and records an auditable recovery event in:

```text
docs/_dependency/hardening/recovery_events.jsonl
```

### External edits after a crash

Automatic recovery never overwrites a post-crash state that cannot be proven to be either the recorded pre-image or a hash written/planned by the interrupted transaction. That includes an unexpected external **deletion** of a file that existed before the transaction. In those cases `recover` stops before changing any target and preserves the external state.

If the operator deliberately chooses transactional rollback over those post-crash edits, the explicit destructive form is:

```bash
docengine recover --force --json
```

The recovery event records `forced=true` and the conflict paths. Automatic recovery performed before normal mutation commands never uses force.

## Runtime-layout migration

P7 introduces a distinct runtime-layout version marker:

```text
docs/_dependency/hardening/runtime_layout.json
```

Current layout version: `1.0.0`.

The previously released P6 runtime had state-schema `1.0.0` but no layout marker. P7 recognizes that layout as `legacy-p6-unmarked` and migrates it **without changing released receipt/baseline/state/event bytes**. It adds only the layout marker and migration audit event.

Explicit migration:

```bash
docengine migrate --json
```

Recognized legacy P6 evidence may also be migrated automatically inside the same exclusive transaction immediately before a normal mutation. Unknown/future layout versions are never reset or guessed.

Machine registry: `spec/registries/MIGRATIONS.json`.

Before migrating released P6 evidence, the migration runtime rejects symlinked/unrecognized evidence and runs the released receipt/baseline/state/event/materialization integrity parsers. It will not create a current-layout marker over corrupt legacy evidence. A migrated marker is cross-checked against both the registered migration ID and its migration audit event; invented migration provenance is invalid.

Migration audit:

```text
docs/_dependency/hardening/migration_events.jsonl
```

## Read-only semantics

The external lock itself does not mutate project files. Project-package bytecode suppression from P6 remains active.

The existing trusted/cooperative project-Python boundary is unchanged: engine-owned read-only paths are protected, but arbitrary project callbacks are not sandboxed. That remains the discoverable A1 deferred hardening policy, not a hidden guarantee.

## Performance baseline

P7 runs `tools/benchmark_p7.py` with the declared 10k-target / 50k-edge fixture and additionally exercises 10k structured diffs and 10k deterministic Markdown renders.

Q7.3 explicitly defers the environment-normalized acceptance budget to P8. Therefore P7 records measurements and keeps P7-A5 `partial` rather than inventing a threshold after observing the result.

## Watch mode

No filesystem watch/daemon mode is introduced in P7. Explicit commands remain canonical per Q7.4.


### Audit-log integrity

`recovery_events.jsonl` and `migration_events.jsonl` are audit evidence, not best-effort logs. Existing history is strictly parsed before append, and `verify` treats malformed or inconsistent hardening event history as a blocking finding rather than silently ignoring it.

## Platform lock support matrix

P8/Q8.E3 closes the former portability watch item for v0.1:

- **POSIX:** shared `fcntl` reader locks and exclusive writer lock; multiple official read-only commands may coexist.
- **Windows:** `msvcrt` fallback safely serializes access; concurrent-reader parity is **not guaranteed**.

Safe Windows serialization is the accepted v0.1 support contract. Shared-reader concurrency parity on Windows is a post-v0.1 optimization, not a release requirement. Data-safety/exclusive-writer guarantees remain required on both backends.


## Corrupt transaction evidence

A transaction journal is recovery authority only after full validation. JSON shape alone is insufficient. Before changing any file, recovery verifies transaction-directory identity, canonical target paths, existed/backup/before-hash relationships, pre-image hashes, and current/planned output hashes. Rogue transaction-root files/symlinks, transaction-id mismatches, impossible operation records, missing/corrupt backups or unknown current states remain `recovery_required`; recovery preserves them for diagnosis and performs no partial rollback.

If synchronous rollback fails, the transaction directory/pre-images remain intact. Cleanup is allowed only after successful rollback or durable commit.

External deletion of a file that existed before the interrupted transaction is an unknown post-crash change, just like unexpected bytes. Default recovery will not recreate it; explicit `recover --force` is required and records the conflict.

Migration/recovery JSONL logs are audit evidence. `verify` validates them and reports corruption as blocking findings while continuing the complete report.
