# AI / CI Usage Protocol — P7

P6 freezes the complete v0.1 operating protocol. An AI/CI consumer should use CLI `--json` as the normal control surface and should not edit `docs/_dependency` state files directly.

## Machine contract

Every JSON response has the schema-2.0.0 top level:

```text
schema_version
command
ok
attention_required
data
warnings
errors
meta
```

Exit policy:

```text
0 success/no blocking attention
2 completed with attention/review remaining
3 verification/domain validation failure
4 usage/project configuration error
5 internal/runtime failure
```

Do not treat every non-zero as a crash. Exit `2` is an expected operating state and must be inspected through the response payload.

## Fresh-agent workflow

1. Read `README.md`, `START_HERE_AGENT.md`, and `OPEN_QUESTIONS_AND_AMBIGUITIES.md`.
2. Run:

```bash
docengine status --json
docengine check --json
```

3. If deterministic/generated work is pending, normally run:

```bash
docengine sync --json
```

4. For every semantic target requiring attention:

```bash
docengine explain TARGET --json
# review target + baseline/current dependency evidence externally
# edit target if necessary using normal project editing tools
docengine explain TARGET --json  # refresh context after any edit
docengine validate TARGET \
  --result still-valid|updated \
  --reason "..." \
  --review-context reviewctx-... \
  --actor-kind ai \
  --json
```

5. Run sync again if deterministic/materialization work remains.
6. Finish with:

```bash
docengine verify --json
```

Work is release-ready only when verify returns `ok=true`, exit `0`, or when blockers are deliberately left unresolved and explicitly reported outside the engine workflow.

## Review authority

Never infer `still-valid` or `updated` automatically from a diff. Structural change evidence and semantic judgment remain distinct. A stale `review_context_id` must be rejected.

## Generated views

Normal regeneration:

```bash
docengine materialize --all --json
```

A deliberate orphan ownership transition is acknowledged without deleting the file or provenance:

```bash
docengine materialize file://PATH --ack-orphan --json
```

## Read-only inspection

Safe inspection commands:

```text
status diff explain history graph resources verify
```

Engine code does not write documentation/runtime state for these commands, and project extension loading suppresses Python bytecode writes. Project callbacks remain cooperative/trusted code under the existing v0.1 model.

## Error handling

When `--json` is present, usage/config/domain/internal errors must remain inside the canonical envelope. Do not parse human stderr/tracebacks as the machine protocol.

`warnings` are non-blocking envelope diagnostics. `errors` explain command execution / usage failures when the failure is represented as an envelope issue; domain-state failures may instead carry their complete evidence in `data` (for example `verify` findings or invalid dependency state). `meta.status` is a stable command status label, while `meta.exit_code` mirrors the process code.


## P7 recovery and migration

If a command returns `recovery_required`, inspect with `verify --json`, then run:

```bash
docengine recover --json
```

Do not use `--force` automatically. `recover --force` is an explicit destructive operator choice when post-crash bytes conflict with the transaction journal.

For explicit runtime migration:

```bash
docengine migrate --json
```

Recognized P6 layout may also migrate automatically inside a normal mutating transaction. Unknown versions must remain failures; never delete `_dependency` to bypass migration.
