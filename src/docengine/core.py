"""Domain-neutral core protocols and compatibility exports."""

from typing import Any, Protocol

from .builders import BuildContext, DerivedObject
from .refs import FieldRef, ResourceRef


class ResourceStore(Protocol):
    def get(self, ref: ResourceRef | str) -> Any: ...
    def version(self, ref: ResourceRef | str) -> str: ...


class ValidationContext(Protocol):
    def current(self, ref: ResourceRef) -> Any: ...
    def baseline(self, ref: ResourceRef) -> Any: ...
    def diff(self, ref: ResourceRef) -> Any: ...


__all__ = [
    "ResourceRef", "FieldRef", "ResourceStore", "BuildContext", "DerivedObject", "ValidationContext"
]
