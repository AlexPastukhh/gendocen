"""Schema validation adapters used by managed resource loading.

The runtime has no mandatory third-party dependencies. The core validator deliberately
implements a documented JSON-Schema subset used by v0.1 contracts. Projects needing
advanced JSON Schema keywords can provide/plug in a richer adapter later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .jsonio import StrictJsonError, load_strict


class SchemaValidationError(ValueError):
    pass


class SchemaResolutionError(ValueError):
    pass


class SchemaValidator(Protocol):
    def validate(self, instance: Any, schema: Mapping[str, Any]) -> None: ...


_IGNORED_ANNOTATION_KEYS = {"$schema", "$id", "title", "description", "default", "examples"}
_SUPPORTED_KEYS = {
    "type", "required", "properties", "additionalProperties", "items", "enum",
    "minLength", "minItems", "maxItems", "uniqueItems", *_IGNORED_ANNOTATION_KEYS,
}


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise SchemaValidationError(f"unsupported JSON Schema type: {expected}")


class CoreSchemaValidator:
    """Strict, dependency-free validator for the v0.1 schema subset."""

    def validate(self, instance: Any, schema: Mapping[str, Any]) -> None:
        self._validate(instance, schema, path="$", root=True)

    def _validate(self, instance: Any, schema: Mapping[str, Any], *, path: str, root: bool = False) -> None:
        if not isinstance(schema, Mapping):
            raise SchemaValidationError(f"{path}: schema node must be an object")
        unknown = set(schema) - _SUPPORTED_KEYS
        if unknown:
            raise SchemaValidationError(
                f"unsupported JSON Schema keyword(s) at {path}: {', '.join(sorted(unknown))}"
            )

        if "enum" in schema and not isinstance(schema["enum"], list):
            raise SchemaValidationError(f"{path}: enum must be an array")
        for keyword in ("minLength", "minItems", "maxItems"):
            if keyword in schema and (not isinstance(schema[keyword], int) or isinstance(schema[keyword], bool) or schema[keyword] < 0):
                raise SchemaValidationError(f"{path}: {keyword} must be a non-negative integer")
        if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
            raise SchemaValidationError(f"{path}: uniqueItems must be boolean")
        if "items" in schema and not isinstance(schema["items"], Mapping):
            raise SchemaValidationError(f"{path}: items must be a schema object")

        expected = schema.get("type")
        if expected is not None:
            if not isinstance(expected, (str, list)) or (isinstance(expected, list) and not all(isinstance(x, str) for x in expected)):
                raise SchemaValidationError(f"{path}: type must be a string or array of strings")
            options = [expected] if isinstance(expected, str) else list(expected)
            if not any(_type_matches(instance, option) for option in options):
                raise SchemaValidationError(f"{path}: expected type {options}, got {type(instance).__name__}")

        if "enum" in schema and instance not in schema["enum"]:
            raise SchemaValidationError(f"{path}: value {instance!r} is not in enum")

        if isinstance(instance, str) and "minLength" in schema and len(instance) < int(schema["minLength"]):
            raise SchemaValidationError(f"{path}: string shorter than minLength")

        if isinstance(instance, dict):
            required = schema.get("required", [])
            if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
                raise SchemaValidationError(f"{path}: required must be an array of strings")
            missing = [name for name in required if name not in instance]
            if missing:
                raise SchemaValidationError(f"{path}: missing required properties {missing}")
            properties = schema.get("properties", {})
            if not isinstance(properties, Mapping):
                raise SchemaValidationError(f"{path}: properties must be an object")
            additional = schema.get("additionalProperties", True)
            if not isinstance(additional, (bool, Mapping)):
                raise SchemaValidationError(f"{path}: additionalProperties must be boolean or schema object")
            for name, subschema in properties.items():
                if name in instance:
                    self._validate(instance[name], subschema, path=f"{path}/{name}")
            extras = set(instance) - set(properties)
            if additional is False and extras:
                raise SchemaValidationError(f"{path}: additional properties not allowed: {sorted(extras)}")
            if isinstance(additional, Mapping):
                for name in extras:
                    self._validate(instance[name], additional, path=f"{path}/{name}")

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < int(schema["minItems"]):
                raise SchemaValidationError(f"{path}: too few items")
            if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
                raise SchemaValidationError(f"{path}: too many items")
            if schema.get("uniqueItems"):
                seen: set[str] = set()
                for item in instance:
                    key = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if key in seen:
                        raise SchemaValidationError(f"{path}: duplicate item violates uniqueItems")
                    seen.add(key)
            if "items" in schema:
                for index, item in enumerate(instance):
                    self._validate(item, schema["items"], path=f"{path}/{index}")


@dataclass(frozen=True, slots=True)
class ProjectSchemaRegistry:
    project_root: Path
    mappings: Mapping[str, str]
    validator: SchemaValidator = CoreSchemaValidator()

    def resolve(self, uri: str) -> tuple[Path, dict[str, Any]]:
        relative = self.mappings.get(uri)
        if relative is None:
            raise SchemaResolutionError(f"schema URI is not registered in docengine.toml: {uri}")
        candidate = (self.project_root / relative).resolve(strict=False)
        try:
            candidate.relative_to(self.project_root.resolve(strict=False))
        except ValueError as exc:
            raise SchemaResolutionError(f"schema path escapes project root: {relative}") from exc
        try:
            schema = load_strict(candidate)
        except StrictJsonError as exc:
            raise SchemaResolutionError(f"cannot load schema {uri} from {relative}: {exc}") from exc
        if not isinstance(schema, dict):
            raise SchemaResolutionError(f"schema must be a JSON object: {uri}")
        return candidate, schema

    def validate(self, uri: str, instance: Any) -> Path:
        path, schema = self.resolve(uri)
        self.validator.validate(instance, schema)
        return path
