# Materialization Model

## 1. Что materialize

Materialization применяется к managed/derived views, а не ко всей документации.

```text
structured resource / derived object
        ↓
renderer
        ↓
Markdown / JSON / HTML / other view
```

## 2. Path ownership

Для structured resource информация о Markdown output находится в самом resource JSON под `$docengine.materialize[]`. Для fully derived file output используется такой же documentation-owned `derived_descriptor` JSON; builder logic остаётся в коде.

Dependency logic в JSON не хранится.

## 3. Regeneration policy

Normal edit:

```text
edit structured source
→ validate
→ dependency check
→ rebuild affected derived objects
→ regenerate affected views
```

Для маленьких проектов допустим простой режим:

```text
any structured change
→ materialize all managed views
```

Release/CI:

```text
delete/ignore generated outputs
→ clean full materialize
→ verify parity
```

## 4. Renderers are presentation-only

Renderer не вычисляет business semantics. Он получает уже валидный object/view-model.

```text
object
├→ MarkdownRenderer
├→ JsonRenderer
├→ HtmlRenderer
└→ UI/API adapter
```

## 5. Generated Markdown is not canonical

Если Markdown является generated view, ручное изменение считается transient и должно быть либо запрещено, либо обнаруживаться parity check как drift.
