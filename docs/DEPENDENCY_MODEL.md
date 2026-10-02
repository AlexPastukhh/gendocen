# Dependency Model

## 1. Dependency semantics live in code

JSON хранит data. Code определяет, как значения используются.

Два способа registration:

### Tracked reads — для computational dependencies

```python
with ctx.build(target_ref):
    a = ctx.read(source_a_field)
    b = ctx.read(source_b_field)
    ctx.emit(compute(a, b))
```

Runtime автоматически создаёт dependency receipt из реально прочитанных values.

### Explicit rules — для semantic/review dependencies

```python
@semantic_dependency(
    target="file://architecture/rationale.md",
    sources=[
        "resource://policy/main#/allowed_methods",
        "file://policies/method_policy.md"
    ],
)
def review_rationale(...):
    ...
```

## 2. Dependency types

- `copy_reference` — target field отражает source field.
- `compute` — deterministic calculation.
- `aggregate` — target строится из collection/many resources.
- `semantic_review` — upstream change требует human/AI review.
- `validity` — upstream change снимает подтверждение актуальности.
- `compatibility` — изменение может изменить сопоставимость versions/methods.

## 3. Granularity

- field
- object/resource
- whole file
- field set / collection as conceptual aggregation semantics

In executable P3 v0.1 receipts, persisted source refs use only the granularities that have canonical addresses today: `field`, `resource`, and `whole_file`. An aggregate over many inputs records the many exact refs it actually consumed. The engine does not invent a virtual collection-ref syntax merely to compress evidence.

Whole-file Markdown dependency не требует structured JSON. `file://` в v0.1 относится только к plain canonical Markdown; structured/derived content адресуется через `resource://`, чтобы не обходить canonical ownership и field-level tracking.

В v0.1 Markdown dependency адресуется только на весь файл. Если зависимость нужна только на часть документа, соответствующая часть должна быть вынесена в structured JSON и зависимость ставится на структурированное поле/объект. Markdown section addressing в v0.1 намеренно отсутствует.

## 4. Dependency Receipt

После успешного build/validation runtime фиксирует:

```json
{
  "target": "resource://economics/E17",
  "validated_at": "...",
  "dependencies": [
    {
      "source": "resource://opportunity/O17#/payout",
      "comparator": "exact",
      "baseline_hash": "...",
      "snapshot_ref": "baseline://..."
    }
  ]
}
```

Receipt создаётся infrastructure автоматически, а не вручную project code.

## 5. Baseline

Baseline хранит **только dependency slice**, реально необходимый target.

Field dependency → snapshot field value.
Whole-file dependency → snapshot file content/normalized representation.
Collection dependency → normalized member set/selected fields.

## 6. Diff

Когда current state отличается от validated baseline, engine вычисляет diff согласно comparator:

- exact scalar diff
- set/list diff
- structured JSON diff
- text/Markdown diff
- collection diff

## 7. State transition

```text
VALID
  ↓ dependency changed
STALE / REVIEW_REQUIRED
  ↓ deterministic target
REBUILD
  ↓ success
VALID
```

или:

```text
STALE / REVIEW_REQUIRED
  ↓ semantic review by AI/human
still-valid OR updated
  ↓
new baseline
  ↓
VALID
```

`stale` означает: target больше не подтверждён относительно current dependency state. Это не автоматический вывод, что target неверен.

## 8. Runtime state vs history

Current state:
`docs/_dependency/state/dependency_state.json`

Append-only history:
`docs/_dependency/events/dependency_events.jsonl`

Receipts/history:
`docs/_dependency/receipts/...`

Baselines:
`docs/_dependency/baselines/...`

Штатные mutations выполняются CLI, а не ручным редактированием state-файлов.


## 9. Executable P3 runtime

See `DEPENDENCY_RUNTIME.md` for the persisted receipt/baseline/state/event contract, comparator behavior, builder-code invalidation and implemented CLI boundary.


## 10. P4 semantic review

Explicit semantic rules and the validation workflow are implemented in `SEMANTIC_REVIEW.md`. Structural invalidation produces review evidence; only an explicit actor decision advances semantic validation.
