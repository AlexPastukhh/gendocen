# Resource Model

## 1. Ресурс не равен файлу

Engine должен адресовать logical resources через `ResourceRef`; физический Markdown/JSON path является storage detail.

Примеры:

```text
resource://policies/method_policy
resource://policies/method_policy#/allowed_methods
file://architecture/rationale.md
```

## 2. Plain resource

Markdown file без structured source. Может не участвовать в engine либо участвовать whole-file/semantic dependency.

## 3. Managed resource

Structured source под `docs/_structured/...` с `$docengine` metadata и domain `data`.

Рекомендуемый metadata:

```json
{
  "$docengine": {
    "resource_id": "architecture.overview",
    "schema": "project://schemas/architecture-overview/v1",
    "materialize": [
      {
        "renderer": "markdown",
        "path": "architecture/overview.md",
        "path_base": "documentation_root"
      }
    ]
  },
  "data": {}
}
```

## 4. Derived resource

Не имеет самостоятельного raw domain source. Создаётся builder из других resources.

Если derived resource **materialize в файл документации**, у него должен быть documentation-owned descriptor JSON под `docs/_structured/...` с `resource_kind: "derived_descriptor"` и `$docengine.materialize[]`. Descriptor не содержит dependency/formula logic; builder для его `resource_id` регистрируется в project code. Это гарантирует, что путь generated Markdown хранится в документационной JSON-модели, а не скрыт в коде.

Derived object, который используется только внутренне и не materialize в файл, descriptor JSON иметь не обязан. Если `derived_descriptor` существует, после загрузки project code для него обязан существовать builder; descriptor `data` не является fallback raw value.

## 5. Canonical ownership

Каждый output должен иметь один canonical owner:

- plain Markdown → сам `.md`;
- managed Markdown → structured resource/object;
- fully derived Markdown → derived descriptor JSON (output ownership/path) + builder code + upstream objects.

Нельзя одновременно считать generated Markdown и JSON независимыми canonical sources.

## 6. Canonical reference syntax

P1 fixed the v0.1 address format; P2 builders now consume the same stable references for tracked reads:

```text
resource://<namespace>/<id>
resource://<namespace>/<id>#/<json-pointer>
file://<documentation-relative-path>
```

For a managed `resource_id` such as `policies.method_policy`, the first dot separates the namespace from the local id, so its canonical resource ref is `resource://policies/method_policy`.

`file://` refs are whole-file only in v0.1 and resolve only to **plain canonical Markdown** from the resource inventory. They cannot be used to bypass `_structured`, `_dependency`, or generated managed views. Section-level Markdown addressing is intentionally absent: if a dependency needs a stable sub-document address, that part is promoted to structured JSON and addressed by a field pointer.

Malformed/ambiguous refs are rejected rather than normalized silently. JSON Pointer escaping follows RFC 6901 (`~0` for `~`, `~1` for `/`).

## 7. Resource inventory

`docengine resources` scans the documentation tree and distinguishes:

- `plain` — standalone Markdown with no managed owner;
- `managed` — structured canonical resource under `_structured`;
- `derived` — documentation-owned derived descriptor whose builder arrives in P2+;
- `generated` — materialization target owned by a managed/derived resource.

A generated Markdown target is not simultaneously reported as a plain canonical document.

`source_hash` in managed-resource inventory fingerprints the physical canonical JSON source file. It is deliberately distinct from dependency versions: a whole `resource://...` dependency is versioned from canonical domain `data`, so storage formatting and `$docengine` materialization metadata do not create false computational changes. Field refs are versioned from the canonical addressed value.

## 8. P2 derived object

P2 builds a new immutable `DerivedObject`; it never writes derived fields back into the descriptor or any raw input. Direct tracked reads, observed input versions, per-dependency comparators, builder id/type/source revision, cooperative tracking assurance and deterministic digests live in in-memory `BuildProvenance`. The serializable envelope is specified by `spec/schemas/DERIVED_OBJECT.schema.json`. Persistent receipts/baselines begin in P3.
