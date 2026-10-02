# Code Model

## 1. Reusable engine code

Core framework provides domain-neutral structures:

- `ResourceRef`, `FieldRef`
- `ResourceCatalog` / resource-store protocol
- schema loader / serializer
- immutable `RawObject`
- immutable `DerivedObject`
- `BuilderRegistry`
- `BuildContext`
- `BuildEngine`
- deterministic build provenance / tracked-read evidence
- P4 `ValidationContext`/semantic rule registry and explicit semantic validation; P5 renderer registry/materialization/sync; later: hardening and final release verification.

## 2. Project-specific code

Project semantics live outside the reusable engine:

```text
project/
  docengine.toml
  docengine_project/
    __init__.py
    schemas/
    builders.py      # or builders/ package
    validators/      # later
    renderers/       # optional P5 project renderers
    dependency_rules/# later
```

`docengine.toml` names the local package with `project_package = "docengine_project"`. It must expose `register_builders(registry)` in P2.

## 3. Builder example

```python
def effective_rate(payout, execution_hours, acquisition_hours):
    return payout / (execution_hours + acquisition_hours)


def build_economics(ctx):
    payout = ctx.read("resource://opportunity/main#/payout")
    execution = ctx.read("resource://opportunity/main#/execution_hours")
    acquisition = ctx.read("resource://measurement/acquisition#/hours")

    return {
        "payout": payout,
        "execution_hours": execution,
        "acquisition_hours": acquisition,
        "effective_rate": effective_rate(payout, execution, acquisition),
    }
```

The formula stays ordinary Python. The context supplies dependency-aware inputs.

## 4. Registration

Canonical form:

```python
def register_builders(registry):
    registry.register(
        "resource://economics/main",
        build_economics,
        builder_id="economics.main",
        dependency_type="compute",
        comparator="exact",
    )
```

Decorator convenience is also available when code already holds a registry:

```python
@registry.builder("resource://economics/main")
def build_economics(ctx):
    ...
```

The explicit registry remains the source of registration truth.

## 5. Tracked versus untracked reads

Dependency-bearing inputs must use `ctx.read()` or `ctx.get()`.

```python
price = ctx.read("resource://catalog/product#/price")  # field dependency
product = ctx.get("resource://catalog/product")        # whole-resource dependency
```

An explicit exceptional `ctx.untracked_read(..., reason=...)` exists, but makes the build provenance incomplete/auditable as such. Arbitrary direct I/O in builder code is a project-code contract violation for dependency tracking.

## 6. Semantic validators

Semantic validator infrastructure is P4. It will consume the same resource-ref/dependency model but will not pretend that semantic text is a computable formula.

## 7. Pure business functions

Keep formulas pure whenever possible. Builders should orchestrate reads and pass plain values into pure helpers. This makes project semantics independently testable and keeps dependency infrastructure out of business formulas.


## Semantic dependency registration (P4)

Project code may expose `register_semantic_dependencies(registry)`. Rules declare target, dependency type, exact sources and comparators. They never contain an engine-generated semantic verdict. See `SEMANTIC_REVIEW.md`.


P7 hardening adds `hardening.py`: external process locking, `FileTransaction`, recovery and runtime-layout migrations. Low-level stores remain implementation primitives; official concurrent mutation semantics are provided through the guarded command/orchestration layer.
