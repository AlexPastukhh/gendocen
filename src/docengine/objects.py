"""Immutable generic object representation for managed structured data."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .refs import ResourceRef


class PointerResolutionError(KeyError):
    pass


class FrozenMapping(Mapping[str, Any]):
    __slots__ = ("_data",)

    def __init__(self, values: Mapping[str, Any]):
        self._data = MappingProxyType({str(key): freeze(value) for key, value in values.items()})

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:  # pragma: no cover - representation helper
        return f"FrozenMapping({self._data!r})"

    def to_builtin(self) -> dict[str, Any]:
        return {key: thaw(value) for key, value in self._data.items()}


def freeze(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return value
    if isinstance(value, Mapping):
        return FrozenMapping(value)
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return value.to_builtin()
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


def resolve_pointer(value: Any, parts: tuple[str, ...]) -> Any:
    current = value
    for token in parts:
        if isinstance(current, FrozenMapping):
            try:
                current = current[token]
            except KeyError as exc:
                raise PointerResolutionError(token) from exc
        elif isinstance(current, tuple):
            if token == "-":
                raise PointerResolutionError("'-' is not valid for reads")
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise PointerResolutionError(token)
            index = int(token)
            try:
                current = current[index]
            except IndexError as exc:
                raise PointerResolutionError(token) from exc
        else:
            raise PointerResolutionError(token)
    return current


@dataclass(frozen=True, slots=True)
class RawObject:
    resource_id: str
    ref: ResourceRef
    source_path: Path
    schema_uri: str | None
    resource_kind: str
    data: FrozenMapping | tuple[Any, ...]

    @classmethod
    def create(
        cls,
        *,
        resource_id: str,
        source_path: Path,
        schema_uri: str | None,
        resource_kind: str,
        data: Any,
    ) -> "RawObject":
        frozen = freeze(data)
        if not isinstance(frozen, (FrozenMapping, tuple)):
            raise TypeError("managed resource data must be an object or array")
        return cls(
            resource_id=resource_id,
            ref=ResourceRef.from_resource_id(resource_id),
            source_path=source_path,
            schema_uri=schema_uri,
            resource_kind=resource_kind,
            data=frozen,
        )

    def read(self, ref: ResourceRef | str) -> Any:
        field_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if field_ref.scheme != "resource" or field_ref.logical_resource_id != self.resource_id:
            raise PointerResolutionError(f"reference does not address {self.resource_id}")
        return resolve_pointer(self.data, field_ref.pointer_parts)

    def to_builtin(self) -> Any:
        return thaw(self.data)
