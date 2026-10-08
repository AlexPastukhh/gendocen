# Architecture

## 1. Purpose

Generic Documentation Engine is a domain-independent runtime for documentation where most files may remain plain Markdown while selected information becomes structured, addressable, dependency-aware and reproducibly generated.

The core separation is:

```text
DATA                 → canonical stored content
SCHEMA               → structured-data shape
PROJECT CODE          → deterministic computation / explicit semantic rules
DEPENDENCY RUNTIME   → evidence, baselines, change state
HUMAN / AI           → semantic judgment
PRESENTATION          → Markdown / custom file views / integration adapters
```

See `CORE_WORKFLOWS.md` first for end-to-end usage and `USE_CASES.md` for atomic contracts.

## 2. Document/resource classes

### Plain Markdown

Independent `.md`; the engine may ignore it completely.

### Plain Markdown + semantic dependency

Markdown remains canonical prose. Project dependency code declares which upstream resource/file slices require the prose to be reviewed again.

### Structured managed document

Canonical data lives under mirrored `docs/_structured/...json`; Markdown is a materialized human-facing view.

### Fully derived document

A `derived_descriptor` owns target identity/materialization path, while a project builder constructs the object from tracked inputs. The generated file is not manually canonical.

## 3. Object pipeline

```text
Structured JSON
        ↓ validate/load
Immutable RawObject
        ↓ project builder / pure helpers
Transient immutable DerivedObject
        ↓ renderer / integration adapter
Markdown / custom managed file / application integration
```

Plain Markdown may bypass the object pipeline entirely.

A successful build persists dependency evidence (receipt/baseline/state/events); it does **not** turn the DerivedObject payload into a canonical persisted object store.

## 4. Dependency pipeline

Deterministic and semantic invalidation are different operations:

```text
builder code                         semantic rule
ctx.read()/ctx.get()                 explicit source refs/comparators
        ↓                                      ↓
actual tracked reads                       review dependency
        └──────────────┬───────────────────────┘
                       ↓
                dependency receipt
                       ↓
              validated baseline slices
                       ↓
                 upstream change
                       ↓
                compare current state
                       ↓
       ┌───────────────┼────────────────┐
       ↓               ↓                ↓
BUILD_REQUIRED   REVIEW_REQUIRED      STALE
compute/copy/    semantic_review/     validity
aggregate        compatibility
       ↓               ↓                ↓
explicit         human/AI review      human/AI review
rebuild/sync     still-valid|updated  still-valid|updated
       └───────────────┴────────────────┘
                       ↓
                      VALID
```

`INVALID` is reserved for unusable/incomplete evidence such as unavailable sources/builders or incomplete audit evidence; it is not a synonym for ordinary staleness.

`check` detects/evaluates this state and may persist state/events. Resolving current derived sources can execute their builders in memory; recording replacement deterministic build receipts and materializing outputs remain explicit rebuild/sync actions. `sync` performs the check, selectively rebuilds deterministic targets that are missing a receipt or are `build_required`, and leaves semantic attention unresolved.

## 5. Raw vs derived invariant

Raw source objects never gain derived fields “in place.”

```text
Raw A + Raw B → Derived C
Raw A + Derived C → Derived D
Derived C + Derived D → Projection E
```

This is required for provenance, reproducibility and debugging.

## 6. Object graph and dependency graph are different

The object/domain graph answers which resources/references exist.

The dependency graph answers which exact field/resource/file states were used to build or validate another target.

Deterministic source edges are runtime-derived from actual `BuildContext` reads. Semantic review edges are explicit project-code rules. Do not maintain a second manual deterministic edge table.

## 7. Project-authoring boundary

Recommended target-oriented mirrored layout:

```text
project/
  docs/<logical/path>.md
  docs/_structured/<logical/path>.json
  docengine_project/builders/<logical/path>.py
  docengine_project/dependency_rules/<logical/path>.py
```

`docengine_project` stays outside the documentation root. Ordinary project dependency authoring should not require edits to `src/docengine/**`.

A builder/rule module must also be imported/registered through the project package registration surface; file placement alone does not make it active.

Project Python is trusted/cooperative code, not a sandbox. Tracking guarantees cover mediated dependency reads, not arbitrary Python side effects.

## 8. Domain independence

Core primitives remain generic:

- `ResourceRef`, `FieldRef`
- resource catalog/store
- `RawObject`, `DerivedObject`
- builder/semantic/renderer registries
- `BuildContext`
- `BuildOperation` — explicit reuse of complete successful builds/provenance within one stable operation
- receipt, baseline, diff, state, event
- materialization and hardening runtimes

Project packages define schemas/models/builders/helpers/renderers/dependency rules.

Independent nested field authoring uses the project-owned [`FieldPlan` recipe](FIELD_DEPENDENCIES.md) over whole internal resources. Atomic providers remain complete computational units; composites gather independent children at root/intermediate levels. CLI evaluation paths share a BuildOperation across resolution/check/rebuild/materialization, then discard it at command completion. In-memory reuse preserves the existing source ownership and persisted ref/receipt contracts.

## 9. Generated-file ownership

Every generated documentation output has an explicit documentation-owned owner. Managed/derived file paths live in `$docengine.materialize[]` under the mirrored structured descriptor. Project code owns computation/dependency semantics but is not the only place where destination ownership is hidden.

Before editing visible Markdown, determine ownership with `docengine resources --json`. Managed/derived views resolve to structured ownership there; if a file is plain, additionally inspect `docengine graph file://PATH --json` for semantic `rules`/`rule_edges`. Generated views are edited through their canonical source/builder, not directly.

## 10. Concrete implementation boundaries

- **P2:** project builder registration, `BuildContext`, immutable transient `DerivedObject`, tracked reads, derived-of-derived and deterministic cycle detection.
- **P3:** persistent receipts/baselines/state/events, comparators/diffs, code-revision invalidation and dependency inspection.
- **P4:** explicit semantic rules/review/validation; engine never invents semantic verdicts.
- **P5:** renderer registry, managed materialization, drift detection and bounded selective `sync`.
- **P6:** complete CLI/AI protocol and project `verify`.
- **P7:** locking, transactions, recovery/migration and hardening audit.
- **P8:** final release verification/performance/package integrity.

Built-in presentation is file-oriented (not a ready live UI/API backend). Project-defined renderers and external application adapters can expose other views without changing canonical ownership.
