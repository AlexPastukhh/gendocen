# P5 Materialization and Sync Runtime

## Purpose

P5 turns documentation-owned structured/derived resources into reproducible generated views and orchestrates the safe deterministic work loop after changes.

Materialization is presentation only: output ownership comes from `$docengine.materialize[]`; renderers never choose arbitrary filesystem paths.

## Renderer registry

The engine provides a deterministic built-in `markdown` renderer. Project code may optionally expose:

```python
def register_renderers(registry):
    registry.register("compact", render_compact)
```

A renderer receives JSON-compatible domain data plus a `RenderContext` containing the owner ref, resource id/kind, renderer id and registered target path. It returns `str` or `bytes`.

Project renderers are revisioned with the project package source revision. Changing renderer code marks the generated view outdated even when canonical data is unchanged.

## Ownership

Generated output is owned only when a managed resource explicitly declares it:

```json
{
  "$docengine": {
    "resource_id": "catalog.product",
    "materialize": [
      {
        "renderer": "markdown",
        "path": "catalog/product.md",
        "path_base": "documentation_root"
      }
    ]
  },
  "data": {}
}
```

Materialization never targets `_structured` or `_dependency`, never escapes the documentation root and refuses symlink replacement.

A plain Markdown file that is not a registered materialization target cannot be overwritten through `materialize`.

## Materialization state and drift

P5 stores machine-owned output provenance at:

```text
docs/_dependency/state/materialization_state.json
```

Each registered output records:

- owner `resource://...` ref;
- renderer id and renderer revision;
- canonical input revision;
- generated output SHA-256 digest;
- managed/derived resource kind.

No visible marker is required inside generated Markdown.

Drift classes:

- `unmaterialized` — registered target has no persisted provenance yet;
- `outdated` — owner input, renderer, renderer revision or resource kind changed;
- `missing` — previously materialized file is gone;
- `drifted` — current bytes no longer match the recorded digest;
- `error` — current input/path/renderer cannot be inspected safely.

`materialize --all` performs a clean full regeneration of all currently registered views. If bytes already match the canonical render, the engine records/updates provenance without rewriting the file.

## Removed/renamed targets

When materialization metadata removes or renames a target, P5 **does not delete the old file**. Once ownership metadata disappeared, that Markdown may have become intentionally canonical/plain content.

The old provenance entry is reported as `orphaned_state`, the file is preserved, and `sync` returns `attention_required`. Destructive orphan cleanup is not automatic in v0.1. A human/agent may resolve the attention state explicitly with `docengine materialize file://PATH --ack-orphan`; this preserves the file and the old ownership/provenance record, adds `orphan_acknowledged=true`, and makes later sync treat that orphan as acknowledged rather than unresolved.

## Rebuild

`docengine rebuild TARGET` executes a registered deterministic builder and records a new P3 dependency receipt/baseline/state. It does not perform semantic review.

Generated views are presentation state; normal orchestration uses `sync` to materialize affected outputs after rebuilds.

## Sync

Default `sync` is affected-only:

1. validate/load current project resources/rules;
2. run structural dependency checks;
3. identify missing or `build_required` deterministic targets;
4. rebuild each selected deterministic target at most once in the sync occurrence;
5. run structural checks again;
6. inspect generated-view drift/outdated state;
7. materialize only affected/drifted/unmaterialized views;
8. leave semantic `review_required`/`stale` targets unresolved;
9. return a machine summary.

`sync --all` keeps deterministic rebuild selection bounded but materializes every currently registered output for explicit full regeneration.

In dev23 the initial check, evidence-advancing rebuilds, final check, drift inspection and materialization share a stable BuildOperation. Resolving derived dependencies during checking can execute builders in memory; the `rebuilt` summary lists targets whose build evidence was advanced. Complete successful values/provenance are reused across these steps. The next command starts a fresh operation. Observed consumed-source/project-code changes abort the operation inside the transaction instead of committing mixed-version output/evidence.

If deterministic work succeeds while semantic review remains, the operation is successful with:

```text
status = attention_required
ok = true
```

P6 freezes the final automation policy: this successful-but-attention-required result uses exit code `2`.

## Mixed semantic ↔ deterministic cycles

P4 rejects pure semantic cycles and P2 builder execution rejects pure deterministic recursion, but a combined graph can contain:

```text
semantic target A → derived builder B → A
```

P5 v0.1 permits such a mixed SCC only with bounded orchestration:

- deterministic members run at most once per sync occurrence;
- semantic members are never auto-accepted;
- an affected mixed SCC returns `attention_required`;
- repeated sync without new changes performs no new deterministic/event/output work;
- all-deterministic executable cycles remain errors.

This resolves P5/Q5.E1 without claiming the combined dependency graph is globally acyclic.

## Idempotency

With unchanged canonical inputs, code, renderer revisions and generated bytes, repeated `sync`:

- records no new deterministic build receipt (current derived sources may still be evaluated in memory);
- appends no dependency events;
- rewrites no generated outputs;
- does not advance materialization state.

## Current CLI boundary

Implemented through P8:

```text
init
resources
status
check
diff
explain
history
graph
validate
rebuild
materialize
sync
verify
recover
migrate
```

`verify` is the P6 read-only complete project report/release-gate query; it does not fix engine-managed state, but may execute trusted unsandboxed project callbacks for reproducibility checks. `recover`/`migrate` are P7 hardening commands. P8 performs final global release-gate consolidation.
