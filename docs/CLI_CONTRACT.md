# CLI Contract — P7 hardened v0.1 protocol

Canonical executable: `docengine`.

P7 preserves the P6 machine protocol and extends the command surface with explicit recovery/migration:

```text
init status check diff explain sync rebuild validate materialize verify history graph recover migrate resources
```

Every command has human output. Every command supports `--json`; when JSON is requested, normal command failures, usage errors and the last-resort internal error boundary return the same versioned envelope rather than a traceback.

## Canonical JSON envelope — schema 2.0.0

```json
{
  "schema_version": "2.0.0",
  "command": "verify",
  "ok": true,
  "attention_required": false,
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "engine_version": "0.1.0.dev17",
    "status": "verified",
    "exit_code": 0
  }
}
```

The exact schema is `spec/schemas/CLI_OUTPUT.schema.json`.

`schema_version` is deliberately **2.0.0**. Earlier phases exposed a different machine envelope while carrying version 1.0.0; P6 freezes the final v0.1 AI/CI protocol with an explicit incompatible version bump rather than silently changing 1.0.0.

`ok` describes the command/domain outcome. `attention_required=true` means the command completed enough to return useful evidence but unresolved review/work remains. Human output is a rendering of the same `CommandResult`; when a failed/attention result already contains diagnostic data (for example invalid state targets), the human surface preserves those facts rather than collapsing them to a status label. It must not invent facts absent from JSON.

## Exit codes

| Exit | Meaning |
| ---: | --- |
| `0` | success; no blocking attention remains for the command result |
| `2` | command completed, but review/attention remains |
| `3` | verification/domain validation failure |
| `4` | usage or project configuration error |
| `5` | internal/runtime failure caught by the CLI protocol boundary |

The JSON `meta.exit_code` always matches the process exit code.

## Common options

All subcommands accept:

```text
--json
--project-root PATH
--docs-root PATH
```

Structured stdin/bulk-action protocol is intentionally out of v0.1. JSON stdout is mandatory for machine use. Explicit `--project-root` and explicit `--docs-root` string values must be non-empty. `--project-root` must name an existing directory; an existing `--docs-root` must also be a directory and remain inside the selected project. Empty explicit root values and other root-shape failures are usage/config errors (exit `4`), never fallback/default selection or clean empty-project success.

## Commands

### `docengine init`

Initialize project configuration/runtime directories without promoting plain Markdown. Mutation: project initialization/config only.

### `docengine status`

Read current dependency state. Read-only. Non-valid current state may produce exit `2` or `3` while still returning the full state payload.

### `docengine check`

Compare current dependencies/rules with validated evidence. May mutate dependency state/events only. It does not perform semantic judgment.

### `docengine diff TARGET`

Read-only baseline-vs-current diff. Missing/malformed target is usage/config error. A changed but inspectable target returns attention exit `2`.

### `docengine explain TARGET`

Read-only dependency explanation or P4 semantic review packet. A review-required/stale target returns attention exit `2`.

### `docengine sync [--all]`

Bounded P5 orchestration: check, deterministic rebuild, affected/full materialization, preserve unresolved semantic review. `attention_required` returns `ok=true`, exit `2`.

### `docengine rebuild TARGET`

Record a deterministic build for one target. Mutation: deterministic receipt/state/events. Invalid/incomplete build evidence is exit `3`.

### `docengine validate TARGET ...`

```text
--result still-valid|updated
--reason TEXT
--review-context ID
[--actor-kind human|ai|ci|unknown]
[--actor-label TEXT]
[--evidence TEXT ...]
```

Explicit human/AI semantic decision. Missing logical inputs are usage exit `4`; stale/invalid review context is domain validation exit `3`.

### `docengine materialize [TARGET|--all] [--ack-orphan]`

Write registered generated views/materialization provenance. `--ack-orphan` requires a file target and is mutually exclusive with `--all`; it preserves the file and historical provenance.

### `docengine verify`

Read-only complete project verification with respect to engine-managed project state. It aggregates all available findings instead of failing fast and **never fixes/advances engine state**. Verification may execute trusted project builders/validators/renderers for reproducibility checks; project Python is not sandboxed, so the read-only contract is not a guarantee against arbitrary callback side effects.

It checks at least:

- persisted dependency receipt/baseline/state/event integrity;
- current dependency/rule state without advancing baselines;
- unresolved semantic review;
- documentation-owned required derived builders/build receipts;
- materialization drift/missing/outdated/error state;
- unresolved orphaned materialization state;
- current builder/semantic/renderer component load failures.

Any blocking finding yields `ok=false`, exit `3`, but a complete report remains in `data.report`. Successful verification yields `ok=true`, exit `0`.

The report schema is `spec/schemas/VERIFICATION_REPORT.schema.json`.

### `docengine history TARGET`

Read-only receipt/event/review history.

### `docengine graph [TARGET]`

Read-only dependency/semantic graph. Persisted graph diagnostics remain available when current project code cannot load.


### `docengine recover [--force]`

Exclusive P7 crash reconciliation. Without `--force`, recovery refuses to overwrite a target that changed outside the interrupted transaction. `--force` explicitly chooses pre-crash rollback and records conflict paths in the recovery audit event.

### `docengine migrate`

Exclusive runtime-layout migration. Released audit evidence is never reset; recognized P6 evidence is validated/preserved and the P7 layout marker/audit event is added. Normal mutations may perform the same recognized migration transactionally before their own work.

### `docengine resources`

Read-only plain/managed/generated/derived inventory.

## Query/mutation boundary

Strictly read-only engine operations (with the trusted-project-code caveat above):

```text
status diff explain history graph resources verify
```

Mutating commands and their allowed engine-owned effects:

```text
init         project initialization/config only
check        dependency state/events
sync         dependency state/events + deterministic receipts + generated views/materialization state
rebuild      deterministic receipt/state/events
validate     semantic receipt/baseline/state/events
materialize  generated views/materialization state
recover      hardening rollback/recovery event under exclusive lock
migrate      versioned runtime-layout migration/audit under exclusive lock
```

Project-owned Python callbacks remain subject to the existing cooperative/trusted-code contract. P7 hardens engine-owned file transactions/concurrency but does not sandbox arbitrary project callbacks; A1 remains deferred.

## Registry

`spec/registries/CLI_COMMANDS.json` is the machine-readable command/flag/mutation/exit-code registry. Acceptance tests compare it with the parser surface.


## P7 locking and transaction boundary

Official CLI read commands use a shared external lock; runtime mutations use an exclusive lock plus write-ahead transaction journal. A conflicting writer/reader returns `runtime_busy` (exit 3) rather than observing a partial commit. See `HARDENING_RUNTIME.md`.
