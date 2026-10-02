# Build Runtime Contract — P2

P2 implements the generic, in-memory builder layer. Persisted receipts/baselines/state remain P3.

## Project registration

`docengine.toml` declares a project-owned Python package:

```toml
[docengine]
project_package = "docengine_project"
```

The package must be a real, non-symlinked package under project root and expose:

```python
def register_builders(registry):
    ...
```

The supplied `BuilderRegistry` is canonical. Decorator registration is convenience only.

A builder target that materializes into documentation must have a documentation-owned `resource_kind="derived_descriptor"` JSON descriptor under `docs/_structured/...`. Internal-only derived objects may exist without any descriptor/JSON. Conversely, every `derived_descriptor` must resolve to a registered builder once project code is loaded; descriptor `data` is not treated as raw domain truth. The descriptor owns documentation output identity/destinations; builder code owns derivation semantics.

## Builder example

```python
def build_total(ctx):
    price = ctx.read("resource://catalog/product#/price")
    rate = ctx.read("resource://catalog/tax_policy#/rate")
    return {
        "price": price,
        "tax_rate": rate,
        "total": price * (1 + rate),
    }


def register_builders(registry):
    registry.register(
        "resource://catalog/price_with_tax",
        build_total,
        builder_id="catalog.price_with_tax",
        dependency_type="compute",
        comparator="exact",
    )
```

Project code may split builders across modules. Dotted packages are supported with normal parent-relative package imports (for example `company.builders` using `from ..common import ...`). The engine loads them under an isolated private module prefix so different projects do not collide in `sys.modules`.

## `BuildContext.read`

`ctx.read(ref, comparator=...)` returns the addressed value and records exactly that ref as a direct dependency. If `comparator` is omitted, the builder registration comparator is the default for that dependency; a builder may override the comparator per read when different inputs require different comparison semantics.

Examples:

```text
resource://catalog/product#/price
resource://policy/main#/allowed_methods
file://architecture/rationale.md
```

In v0.1 `file://` may address only **plain canonical Markdown**. Managed/derived documentation and files under `_structured`/`_dependency` are addressed through `resource://` or runtime APIs, never by reading their storage file as a plain dependency.

If the ref addresses a derived target, the dependency is built recursively and the requested derived slice is recorded.

Fields not read through tracked APIs do not appear in dependency evidence.

## `BuildContext.get`

`ctx.get(resource_ref, comparator=...)` accepts a whole structured-resource ref only. It returns a `RawObject` or `DerivedObject` and records a whole-resource dependency. The optional comparator behaves the same way as on `read()`.

If code obtains an object via `get()` and then reads individual fields from that returned object, the captured dependency intentionally remains whole-resource because that was the granularity explicitly requested through the tracked API.

For raw structured resources, the whole-resource dependency version is the canonical hash of the resource **domain `data`**, not the physical JSON bytes or `$docengine` envelope. Reformatting JSON or changing materialization metadata therefore does not invalidate a computational dependency whose domain object is unchanged. `source_hash` remains a separate physical-file hash for inventory/source provenance. Infrastructure fields on `RawObject`/`DerivedObject` are diagnostic metadata, not supported semantic builder inputs; if such information must affect derivation, model it explicitly as structured data/dependency.

## Explicit untracked escape hatch

Python project code cannot be sandboxed from arbitrary filesystem/I/O access. Dependency-bearing inputs are therefore a programming contract: they must use the context.

For an intentional legacy/exception path, use:

```python
ctx.untracked_read(ref, reason="legacy helper")
```

This does **not** create normal dependency evidence. Instead provenance records the untracked access and sets `audit_complete=false`. Direct filesystem/network reads that bypass the context entirely are outside the auditable contract. P2 therefore exposes `tracking_assurance="cooperative"` in provenance: `audit_complete=true` means there are no **known** tracking gaps under the required context-usage contract; it is not a sandbox proof that arbitrary Python performed no hidden I/O.

## Raw vs derived

Raw inputs are never mutated. Builder output is copied/frozen into a new immutable `DerivedObject`.

```text
raw + raw         -> derived
raw + derived     -> derived
derived + derived -> derived/projection
```

Derived output must be JSON-compatible object/array data with string object keys and finite numeric values.

## Provenance

Every P2 `DerivedObject` contains deterministic in-memory `BuildProvenance`:

- builder id;
- builder/source revision (`sha256:...` for project packages; direct synthetic registries may be explicitly `unversioned`);
- target ref;
- dependency type;
- builder default comparator id;
- tracking assurance (`cooperative` in v0.1);
- exact direct tracked refs plus their observed versions and per-dependency comparator;
- explicit untracked accesses;
- output digest;
- provenance digest.

No timestamp is included in deterministic build provenance. The project-package source revision is content-addressed from project Python source so changing builder/helper code changes provenance even when JSON inputs do not. Rebuilding unchanged inputs with unchanged builder source produces equivalent output/provenance.

`DerivedObject.to_envelope()` is validated by `spec/schemas/DERIVED_OBJECT.schema.json`.

## Derived-of-derived resolution

A read of a registered derived target recursively invokes its builder in the same build session. One build session caches a derived target once.

P2 records **direct** dependencies for each derived object. Transitive provenance remains available through the provenance of downstream derived inputs; P3 will persist receipts/graph state.

## Cycles

Cycles are configuration/build errors in v0.1. The engine reports the exact deterministic cycle path, for example:

```text
resource://derived/a -> resource://derived/b -> resource://derived/a
```

It must never rely on Python recursion failure as cycle detection.

## P2 persistence boundary

P2 does **not** persist:

- dependency receipts;
- baselines;
- dependency state/events;
- built derived objects as canonical runtime state.

Those begin in P3/P5 according to the implementation plan. P2 proves the build semantics and dependency evidence in memory first.


## P3 persistence

P2 build execution remains ordinary Python logic, but P3 can persist a successful `DerivedObject` as a dependency receipt. Exact values observed by tracked reads are carried in-memory only long enough to create content-addressed dependency-slice baselines. The public provenance envelope exposes a digest, not the full snapshot value.

Builder code revision is a first-class invalidation input. P3 compares the recorded `builder_revision` to the current project package revision and marks deterministic targets `build_required` when code changed.
