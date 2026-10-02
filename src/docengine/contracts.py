"""Specification contract validation helpers used by P0 tests and tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    pass


def load_json(path: str | Path) -> Any:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON contract {source}: {exc}") from exc


def validate_schema_instance(instance: Any, schema: dict[str, Any]) -> None:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - environment-specific guidance
        raise ContractError("jsonschema is required for specification contract validation") from exc
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.exceptions.SchemaError as exc:
        raise ContractError(f"invalid JSON Schema: {exc.message}") from exc
    except jsonschema.exceptions.ValidationError as exc:
        raise ContractError(f"contract validation failed: {exc.message}") from exc
