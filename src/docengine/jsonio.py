"""Strict JSON helpers for canonical documentation data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class StrictJsonError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"non-standard JSON numeric constant is not allowed: {value}")


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise StrictJsonError(f"JSON number is outside finite runtime range: {value}")
    return parsed


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key is not allowed: {key!r}")
        result[key] = value
    return result


def loads_strict(text: str, *, source: str = "<json>") -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant, parse_float=_parse_float, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, StrictJsonError) as exc:
        raise StrictJsonError(f"invalid canonical JSON {source}: {exc}") from exc


def load_strict(path: str | Path) -> Any:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise StrictJsonError(f"cannot read JSON {source}: {exc}") from exc
    return loads_strict(text, source=str(source))
