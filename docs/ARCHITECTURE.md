# Architecture

## 1. Назначение

Generic Documentation Engine — domain-independent runtime для документации, где часть информации остаётся plain Markdown, а часть получает structured representation и программно управляемые dependencies.

Главное разделение:

```text
DATA                 → что сохранено
SCHEMA               → какую форму имеют structured data
CODE                 → как строятся/проверяются зависимости
DEPENDENCY RUNTIME   → что изменилось относительно validated baseline
HUMAN / AI           → semantic judgment
RENDERERS            → Markdown / JSON / HTML / UI / API
```

## 2. Типы документов

### Plain Markdown
Самостоятельный `.md`; engine может его полностью игнорировать.

### Plain Markdown + semantic dependency
Markdown остаётся самостоятельным, но dependency code регистрирует, какие upstream resources/fields делают его требующим повторной проверки.

### Structured managed document
Canonical data живёт в `docs/_structured/...json`; Markdown является materialized human view.

### Fully derived document
Документ строится целиком builders/renderers из других objects; вручную не редактируется.

## 3. Object pipeline

```text
Structured JSON/YAML/etc.
        ↓ validate
Generic loader
        ↓
Immutable raw objects
        ↓
Builders / validators
        ↓
Derived / projection objects
        ↓
Renderers
        ↓
Markdown / JSON API / HTML / UI
```

Plain Markdown может обходить object pipeline полностью.

## 4. Dependency pipeline

```text
builder/validator code
        ↓
dependency-aware reads / explicit semantic dependency declarations
        ↓
Dependency Receipt
        ↓
Validated baseline slices
        ↓
upstream change
        ↓
diff old baseline vs current slice
        ↓
mark affected target stale/review_required
        ↓
rebuild deterministic OR semantic review by AI/human
        ↓
new baseline
```

## 5. Raw vs derived

Raw source object никогда не получает derived field "на месте".

```text
Raw A + Raw B → Derived C
Raw A + Derived C → Derived D
Derived C + Derived D → Projection E
```

Это обязательный invariant для provenance, reproducibility и debugging.

## 6. Object graph и dependency graph — разные вещи

Object graph отвечает: какие сущности/refs существуют.

Dependency graph отвечает: какие конкретные field/resource states были использованы для build/validation другого target.

Dependency graph должен быть runtime-derived из фактических reads и explicit semantic dependency rules, а не поддерживаться вручную как большая таблица.

## 7. Domain independence

Runtime не должен знать терминов конкретного проекта (`Opportunity`, `Measurement`, `Contract`, `APIEndpoint`). Он знает только универсальные primitives:

- ResourceRef
- FieldRef
- ResourceStore
- RawObject
- DerivedObject
- Builder
- Validator
- Renderer
- DependencyReceipt
- Baseline
- Diff
- DependencyState
- Event

Project package определяет schemas/models/builders/validators/renderers/dependency rules.

## Generated-file ownership rule

Любой generated documentation file должен иметь явного documentation-owned owner. Для managed/fully-derived file outputs materialization path хранится в JSON descriptor под documentation root; code содержит builder/dependency semantics, но не является единственным местом, где спрятан destination path.

## P2 concrete build boundary

P2 implements the builder path shown above as an in-memory deterministic runtime: project-local builder registration, `BuildContext` tracked reads, immutable `DerivedObject`, direct provenance and cycle detection. Persistent receipts/baselines/state remain P3; materialization execution remains P5. See `BUILD_RUNTIME.md`.


## P5 concrete materialization boundary

P5 adds deterministic renderers, documentation-owned materialization provenance, drift detection and bounded `sync`. Renderers perform presentation only; output paths come from documentation-owned `$docengine.materialize[]`. Sync rebuilds deterministic targets from dependency evidence but never fabricates P4 semantic acceptance. See `MATERIALIZATION_RUNTIME.md`.
