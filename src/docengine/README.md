# Runtime implementation

P0 through P8 are implemented here.

Implemented through P8:

- version constants and stable machine-output envelope;
- safe project/documentation-root discovery and `docengine.toml` parsing;
- idempotent `docengine init` without plain-Markdown promotion;
- strict canonical JSON loading;
- managed-resource envelope/project-schema validation;
- stable `ResourceRef`/`FieldRef` parsing;
- immutable generic `RawObject` values;
- mirrored `_structured` enforcement and materialization path confinement;
- deterministic `ResourceCatalog`, resolver/version helpers and `docengine resources`;
- project-local package loading via `project_package`;
- explicit `BuilderRegistry` plus decorator convenience;
- dependency-aware `BuildContext.read/get`;
- immutable `DerivedObject` with deterministic in-memory provenance;
- raw+raw, raw+derived and derived+derived builds;
- explicit untracked-read escape hatch with incomplete-audit provenance;
- deterministic dependency-cycle detection with exact cycle path.

P3 also adds content-addressed dependency baselines, deterministic receipts, comparator/diff runtime, persisted dependency state/events, reverse graph/integrity diagnostics, builder-revision invalidation, and operational `status/check/diff/explain/history/graph`.

P4 also adds code-owned semantic rules, machine-readable review packets, review-context protected `still-valid|updated` validation, and actor/reason/evidence history.

P5+ adds materialization/sync, full workflow orchestration and hardening.

P5 adds `materialization.py`: renderer registry, generic Markdown rendering, materialization digest/provenance state, drift inspection, deterministic rebuild and bounded affected/full sync. P6 implements complete read-only `verify`; P7 adds locking, transactions, recovery and migrations in `hardening.py`.

P6 completes the canonical CLI/AI protocol: machine envelope schema 2.0.0, stable exit codes 0/2/3/4/5, JSON usage/internal error boundaries, and read-only complete `verify`.

P7 adds `hardening.py`: external shared/exclusive locks, write-ahead rollback transactions, recovery, runtime-layout migration registry and migration audit.

P8 adds final release tooling under `tools/` and does not change project semantic authority: normalized performance gate, release manifest validation, lifecycle check and global axis closure.
