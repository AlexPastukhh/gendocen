# Phase Execution / Acceptance Model

## Canonical record

Каждый шаг разработки имеет canonical JSON record в `plan/phase_records/P<n>_EXECUTION_RECORD.json`.

В одном record рядом хранятся:

- scope / out-of-scope;
- deliverables;
- mapped acceptance axes;
- acceptance criteria и их evidence;
- pre-execution questions;
- **answer и decision рядом с исходным question**;
- emergent questions, возникшие во время реализации;
- implementation log/evidence;
- axis reviews;
- итоговое acceptance decision.

Исходный `question` после появления ответа не переписывается. Заполняются `answer`, `decision`, `evidence_refs`, `status`.

## Question lifecycle

```text
pending question
    ↓ user/architecture answer
answered + decision recorded
    ↓ implementation
acceptance evidence
```

У вопроса есть `owner`: `user` или `implementer`. Технические решения, которые не требуют продуктового выбора, implementer закрывает сам и оставляет decision рядом с question. Если вопрос возник уже во время coding, он добавляется в `emergent_questions` того же phase record. Blocking question с `pending/deferred` запрещает `accepted`.

## Acceptance lifecycle

```text
planned
→ in_progress
→ acceptance_review
→ accepted | blocked
```

Перед `accepted` нужно:

1. выполнить acceptance criteria;
2. приложить evidence refs (tests, fixtures, command output, files, audit notes);
3. заполнить `axis_reviews` для mapped axes;
4. закрыть blocking questions;
5. обновить `acceptance_summary`;
6. обновить README/System Map/manifest, если phase меняет user-visible behavior.


## Phase-local axis review vs global axis closure

`axis_reviews[].status=pass` внутри P0–P7 означает: применимая к этому phase часть риска проверена и не имеет открытого finding, блокирующего сам phase. Это **не** утверждение, что вся DAX-ось движка уже реализована. Например P0 может пройти DAX13 за стабильный machine-readable envelope и handoff contract, хотя реальные `status/check/validate/verify` semantics появляются позже.

Глобальное состояние осей накапливается по фазам. P8 обязан выполнить consolidated review каждой `release_gate=true` оси по уже реализованной системе целиком. Поэтому в промежуточных отчётах полезно различать `phase-scope PASS` и `global progress PARTIAL`.

## Tests != acceptance

Tests являются evidence для acceptance, но не заменяют проверку архитектурных инвариантов, документации, path safety, AI usability, release integrity и отсутствия scope regression.

## Final release rule

P8 is the only final release/handoff phase. It runs after P7 hardening and must record a consolidated review for **every** DAX axis marked `release_gate=true`, even when evidence originated in an earlier phase.
