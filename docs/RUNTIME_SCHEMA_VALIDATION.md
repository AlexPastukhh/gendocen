# Runtime Schema Validation — P1

Managed JSON has two validation layers.

1. **Engine envelope validation** checks `$docengine`, `resource_id`, `resource_kind`, `materialize`, data shape, canonical refs and confined materialization paths.
2. **Project data validation** is selected by `$docengine.schema` and resolved through `[schemas]` in `docengine.toml`.

Canonical JSON parsing is strict: duplicate object keys and non-standard numeric constants (`NaN`, `Infinity`, `-Infinity`) are rejected.

P1 intentionally keeps the runtime dependency-free. `CoreSchemaValidator` implements an explicit JSON-Schema subset and rejects unsupported keywords; it does not claim full JSON Schema 2020-12 conformance. The adapter boundary is `SchemaValidator`, so projects/later engine versions can supply a complete validator without changing resource files or builders.

Canonical JSON parsing also rejects duplicate keys, `NaN`/`Infinity`, and numeric literals that overflow the runtime finite floating-point range.
