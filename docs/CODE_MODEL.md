# Code Model

## 1. Reusable engine code

`src/docengine/**` provides domain-neutral infrastructure:

- `ResourceRef`, `FieldRef`
- resource catalog / resolver
- schema loader / serializer
- immutable `RawObject` / transient immutable `DerivedObject`
- builder/semantic/renderer registries
- `BuildContext` and deterministic build engine
- dependency receipts/baselines/state/diffs/history
- semantic validation runtime
- materialization/sync/verification
- locking/transaction/recovery/migration hardening

Project-specific formulas and documentation relationships do not belong in the core runtime.

## 2. Project-specific code: accepted mirrored layout

Normal project semantics live outside the reusable engine and mirror the produced documentation target:

```text
project/
  docengine.toml
  docs/
    architecture/
      system_summary.md
    _structured/
      architecture/
        system_summary.json
  docengine_project/
    __init__.py
    schemas/
    builders/
      architecture/
        system_summary.py
    dependency_rules/
      architecture/
        rationale.py
    renderers/
    validators/
```

The target path should tell a human/AI where its descriptor and project code live.

`docengine.toml` names the project package with `project_package = "docengine_project"`. The package remains outside the documentation root.

## 3. Registration is separate from placement

Creating `docengine_project/builders/architecture/system_summary.py` is not sufficient. The module must be imported/registered through the package surface.

Example nested package:

```python
# docengine_project/builders/architecture/system_summary.py

def build_system_summary(ctx):
    title = ctx.read("resource://architecture/overview#/title")
    return {"title": title}


def register(registry):
    registry.register(
        "resource://architecture/system_summary",
        build_system_summary,
        builder_id="architecture.system_summary",
        dependency_type="compute",
        comparator="exact",
    )
```

```python
# docengine_project/builders/__init__.py
from .architecture.system_summary import register as register_system_summary


def register(registry):
    register_system_summary(registry)
```

```python
# docengine_project/__init__.py

def register_builders(registry):
    from .builders import register
    register(registry)
```

Semantic rules use the same target-oriented pattern through `register_semantic_dependencies(registry)`.

## 4. Builder example and tracked reads

Keep formulas ordinary/pure Python while the context mediates dependency-bearing reads:

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

`ctx.read("resource://...#/field")` records field-level evidence. `ctx.get("resource://...")` records a whole-resource dependency and should be used only when the target intentionally depends on the whole object.

## 5. Do not bypass tracking for dependency-bearing inputs

Bad normal authoring pattern:

```python
with open("docs/_structured/catalog/product.json") as f:
    ...
```

or hidden network/database/file reads inside helpers. If the output depends on that value but the runtime did not mediate the read, the receipt cannot reliably invalidate the target.

An explicit exceptional `ctx.untracked_read(..., reason=...)` exists for acknowledged cases and reduces audit completeness; it must not be used to pretend an untracked dependency is safe.

## 6. Raw/derived ownership

Do not write a computed field back into raw canonical JSON merely because its current value is known. Raw sources own observations/input data; deterministic formulas create new `DerivedObject` values.

The builder result is transient. Persistent build evidence is receipt/baseline/state/events; generated file views are owned by materialization metadata.

## 7. Renderers are presentation-only

Builders/helpers compute. Renderers format an already-built object/view model. Moving dependency computation into renderer code hides it from the intended build/provenance model and prevents clean multi-view reuse.

## 8. Semantic dependencies

Project code may expose:

```python
def register_semantic_dependencies(registry):
    ...
```

Rules declare target, dependency type, exact sources and comparators. They do not contain an engine-generated semantic verdict. Human/AI review remains explicit. See `SEMANTIC_REVIEW.md`.

## 9. Code revision invalidation

Current v0.1 project extension loading computes a conservative package-wide source revision. A project-Python edit may therefore mark multiple/all deterministic builders `build_required` even when only one mirrored module changed. This is safe over-invalidation; it is not evidence that their data dependencies are shared.

Per-builder code-dependency revisions are a possible future optimization, not the current contract.

## 10. Trust boundary

`docengine_project/**` is trusted/cooperative Python, not sandboxed execution. It can technically perform arbitrary side effects. Normal AI authoring should stay inside the documented project-owned extension/data paths, use tracked reads and finish with `sync`/`verify`; this organizational boundary does not claim physical prevention of malicious Python.
