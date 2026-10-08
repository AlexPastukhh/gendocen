# Runtime Migration Contract

Canonical/document data is never reset as a migration strategy.

Released receipts, baselines, state and history are audit evidence. Once released, an incompatible persistence/layout change requires a registered migration or an explicit unsupported-version failure.

## Versions

These are distinct concepts:

- `PERSISTED_STATE_SCHEMA_VERSION` — schema carried by released receipt/baseline/state artifacts;
- `RUNTIME_LAYOUT_VERSION` — hardening/layout ownership version for the runtime tree;
- `MACHINE_OUTPUT_SCHEMA_VERSION` — CLI JSON envelope.

P7 keeps released state schema at `1.0.0`, machine output at `2.0.0`, and introduces runtime layout `1.0.0`.

Dev24 adds the separately versioned transaction preparation/cleanup protocol
documented in [Hardening Runtime](HARDENING_RUNTIME.md#safe-preparation-and-retirement-dev24).
It preserves active journal schema 1.0.0 and existing layout marker/provenance.
The side namespaces contain no dependency receipts or target rollback authority;
cleanup tickets authorize only retirement of already completed transactions.
No released evidence or existing marker is rewritten. Old active journals recover
through the same parser and are retired safely by dev24. Older engines do not
maintain the new side namespaces; resume maintenance with the updated runtime.

## Registered P7 migration

`legacy-p6-unmarked → 1.0.0`

The migration validates the released P6 evidence files and preserves their bytes. Validation is strict: symlinked/unrecognized evidence is rejected; dependency receipt/baseline/state/event integrity and materialization state are parsed with the released runtime contracts before a current-layout marker is written. It adds `runtime_layout.json` and a migration audit event. Receipt IDs, baseline hashes, dependency state, event history and materialization state are not rewritten.

See `spec/registries/MIGRATIONS.json`.

## Unknown versions

Unknown/future layout versions produce `migration_failed`; the engine does not silently delete/reinitialize runtime evidence.


## Migration provenance integrity

A migrated `runtime_layout.json` is not trusted merely because its JSON shape is valid. Runtime loading cross-checks `migrated_from` and `migration_id` against `spec/registries/MIGRATIONS.json` and requires a matching migration audit event. A marker with invented/unknown migration provenance is invalid and blocks verification/mutation.

Migration/recovery event histories are strict audit evidence. Corrupt JSONL or invalid event fields are blocking verification findings; the engine never silently truncates or replaces released history.


## Provenance validation

A runtime-layout marker is not self-authenticating. For migrated layouts, `migrated_from`, `migration_id`, and `runtime_layout_version` must correspond to a registered migration. Unknown provenance is invalid.

Before writing a migrated/current marker, the migration validates released evidence paths and integrity. Symlinked receipts/baselines/state/events or structurally/integrity-corrupt released artifacts cause `migration_failed`; the engine writes no current marker and never silently excludes unsafe evidence from the preservation set.

`verify` validates migration/recovery audit JSONL and contains corrupted dependency evidence as blocking report findings rather than turning verification into an internal error.
