"""Copyable field/path composition helper; evaluation and cache belong to the engine."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from docengine.builders import BuilderError
from docengine.objects import RawObject, thaw
from docengine.refs import ResourceRef, format_json_pointer, parse_json_pointer


class FieldPlanError(BuilderError):
    """Invalid ownership, composition or unavailable required input."""


@dataclass(frozen=True)
class _Input:
    source: ResourceRef


@dataclass(frozen=True)
class _Computed:
    target: ResourceRef
    producer: Callable[[Any, FieldPlan], Any]
    raw_override: ResourceRef | None


_MISSING = object()


class FieldPlan:
    """Explicit atomic providers and inferred composite ancestors.

    Legacy field names are literal top-level keys. Path APIs use JSON Pointer.
    Bind canonical raw documents before registration to enable composite reads.
    """

    def __init__(self):
        self._providers = {}
        self._targets = set()
        self._documents = {}
        self._composites = {}
        self._sealed = False

    def _open(self):
        if self._sealed:
            raise FieldPlanError("declare all fields before registering the plan")

    @staticmethod
    def _document(document):
        if not isinstance(document, str) or not document.strip():
            raise FieldPlanError("document names must be non-empty strings")
        return document

    @staticmethod
    def _legacy(field):
        if not isinstance(field, str) or not field.strip():
            raise FieldPlanError("field names must be non-empty strings")
        return (field,)

    @staticmethod
    def _ref(value, *, whole=False):
        ref = ResourceRef.parse(value) if isinstance(value, str) else value
        if (not isinstance(ref, ResourceRef) or ref.scheme != "resource"
                or (whole and ref.pointer_parts) or (not whole and not ref.pointer_parts)):
            kind = "whole resource" if whole else "resource field"
            raise FieldPlanError(f"expected a {kind} ref: {value}")
        return ref

    @staticmethod
    def _at(ref, parts):
        return ResourceRef(scheme="resource", namespace=ref.namespace,
                           resource_id=ref.resource_id, pointer_parts=ref.pointer_parts + parts)

    @staticmethod
    def _label(document, parts):
        return f"{document}.{parts[0]}" if len(parts) == 1 else document + "#" + format_json_pointer(parts)

    @staticmethod
    def _prefix(parent, child):
        return child[:len(parent)] == parent

    def document(self, document, raw_source):
        """Bind a canonical raw object/array for root and nested composition."""
        self._open()
        document = self._document(document)
        if document in self._documents:
            raise FieldPlanError(f"duplicate document binding: {document}")
        self._documents[document] = self._ref(raw_source, whole=True)

    def _declare(self, document, parts, provider):
        self._open()
        key = (self._document(document), parts)
        if not parts:
            raise FieldPlanError("providers must address a field; root is a composite")
        for (doc, path) in self._providers:
            if doc != document:
                continue
            if path == parts:
                raise FieldPlanError(f"duplicate provider for {self._label(document, parts)}")
            if self._prefix(path, parts) or self._prefix(parts, path):
                raise FieldPlanError(f"overlapping atomic providers: {self._label(document, path)} / {self._label(document, parts)}")
        if isinstance(provider, _Computed):
            target = str(provider.target)
            if target in self._targets:
                raise FieldPlanError(f"computed fields must have distinct targets: {target}")
            self._targets.add(target)
        self._providers[key] = provider

    def input(self, document, field, source):
        self._declare(document, self._legacy(field), _Input(self._ref(source)))

    def input_path(self, document, path, source):
        self._declare(document, parse_json_pointer(path), _Input(self._ref(source)))

    def computed(self, document, field, target, producer, *, raw_override=None):
        override = self._ref(raw_override) if raw_override is not None else None
        if override is not None and len(override.pointer_parts) != 1:
            raise FieldPlanError("raw_override must address one top-level raw field; use computed_path for nesting")
        self._computed(document, self._legacy(field), target, producer, override)

    def computed_path(self, document, path, target, producer, *, raw_override=None):
        override = self._ref(raw_override) if raw_override is not None else None
        self._computed(document, parse_json_pointer(path), target, producer, override)

    def _computed(self, document, parts, target, producer, override):
        if not callable(producer):
            raise FieldPlanError("field producer must be callable")
        self._declare(document, parts, _Computed(self._ref(target, whole=True), producer, override))

    @staticmethod
    def _lookup(value, parts):
        current = value
        for token in parts:
            if isinstance(current, Mapping):
                if token not in current:
                    return _MISSING
                current = current[token]
            elif isinstance(current, (list, tuple)):
                if not token.isdigit() or (len(token) > 1 and token.startswith("0")) or int(token) >= len(current):
                    raise FieldPlanError(f"invalid array index: {token}")
                current = current[int(token)]
            else:
                raise FieldPlanError(f"container shape conflict at {format_json_pointer(parts)}")
        return current

    def read(self, ctx, document, field):
        document, parts = self._document(document), self._legacy(field)
        ref = self._read_ref(document, parts)
        try:
            return ctx.read(str(ref))
        except KeyError as exc:
            raise FieldPlanError(f"required input {self._label(document, parts)} is missing: {ref}") from exc

    def read_path(self, ctx, document, path):
        document, parts = self._document(document), parse_json_pointer(path)
        ref = self._read_ref(document, parts)
        try:
            return ctx.read(str(ref))
        except KeyError as exc:
            raise FieldPlanError(f"required input {self._label(document, parts)} is missing: {ref}") from exc

    def _read_ref(self, document, parts):
        for (doc, path), provider in self._providers.items():
            if doc != document or not self._prefix(path, parts):
                continue
            tail = parts[len(path):]
            return (self._at(provider.source, tail) if isinstance(provider, _Input)
                    else self._at(provider.target, ("value",) + tail))
        target = self._composites.get((document, parts))
        if target is not None:
            return self._at(target, ("value",))
        raise FieldPlanError(f"no declared provider for {self._label(document, parts)}")

    @staticmethod
    def _raw(ctx, ref):
        raw = ctx.get(str(ref))
        if not isinstance(raw, RawObject):
            raise FieldPlanError(f"expected a canonical raw input: {ref}")
        return raw

    @classmethod
    def _assign(cls, value, parts, item):
        current = value
        for token in parts[:-1]:
            if isinstance(current, dict):
                if token not in current:
                    current[token] = {}
                current = current[token]
            elif isinstance(current, list):
                cls._lookup(current, (token,))
                current = current[int(token)]
            else:
                raise FieldPlanError(f"container shape conflict at {format_json_pointer(parts)}")
        token = parts[-1]
        if isinstance(current, dict):
            current[token] = thaw(item)
        elif isinstance(current, list):
            cls._lookup(current, (token,))
            current[int(token)] = thaw(item)
        else:
            raise FieldPlanError(f"container shape conflict at {format_json_pointer(parts)}")

    def compose(self, ctx, document, raw_source=None, *, path=""):
        """Return a private, complete root/subtree; no partial result is published."""
        document = self._document(document)
        source = self._documents.get(document)
        if raw_source is not None:
            explicit = self._ref(raw_source, whole=True)
            if source is not None and source != explicit:
                raise FieldPlanError(f"raw source differs from document binding: {document}")
            source = explicit
        if source is None:
            raise FieldPlanError(f"no canonical raw binding for document {document}")
        parts = parse_json_pointer(path)
        keys = [key for key in self._providers if key[0] == document and self._prefix(parts, key[1])]
        if not keys and document not in self._documents:
            raise FieldPlanError(f"no declared fields for document {document} at {path}")
        raw = self._raw(ctx, source)
        base = self._lookup(raw.data, parts)
        result = {} if base is _MISSING else thaw(base)
        if not isinstance(result, (dict, list)):
            raise FieldPlanError(f"container shape conflict at {document}#{path}")
        for _, field in keys:
            provider = self._providers[(document, field)]
            if isinstance(provider, _Computed):
                present = self._lookup(raw.data, field)
                if present is not _MISSING and provider.raw_override != self._at(source, field):
                    raise FieldPlanError(f"raw field conflicts with computed {self._label(document, field)}; declare matching raw_override")
            relative = field[len(parts):]
            if not relative:
                raise FieldPlanError("compose addresses an atomic provider; use read_path")
            self._assign(result, relative, self.read_path(ctx, document, format_json_pointer(field)))
        return result

    def register(self, registry):
        self._open()
        # Validate all generated identities before mutating the registry.
        for doc, source in self._documents.items():
            self._composites[(doc, ())] = self.object_target(doc, "")
            for (document, parts), provider in self._providers.items():
                if document != doc:
                    continue
                if isinstance(provider, _Computed) and provider.raw_override is not None and provider.raw_override != self._at(source, parts):
                    raise FieldPlanError(f"raw_override differs from canonical binding for {self._label(doc, parts)}")
                for count in range(len(parts)):
                    key = (doc, parts[:count])
                    self._composites[key] = self.object_target(doc, format_json_pointer(key[1]))
        all_targets = self._targets | {str(ref) for ref in self._composites.values()}
        if len(all_targets) != len(self._targets) + len(self._composites) or any(registry.has_target(ref) for ref in all_targets):
            raise FieldPlanError("field/composite target collision with existing registry")
        self._sealed = True
        for (document, parts), provider in self._providers.items():
            if not isinstance(provider, _Computed):
                continue

            def build(ctx, spec=provider, doc=document, field=parts):
                bound = self._documents.get(doc)
                if bound is not None:
                    raw = self._raw(ctx, bound)
                    present = self._lookup(raw.data, field)
                    if present is not _MISSING and spec.raw_override != self._at(bound, field):
                        raise FieldPlanError(f"raw field conflicts with computed {self._label(doc, field)}; declare matching raw_override")
                if spec.raw_override is not None:
                    source = ResourceRef.from_resource_id(spec.raw_override.logical_resource_id)
                    raw = self._raw(ctx, source)
                    present = self._lookup(raw.data, spec.raw_override.pointer_parts)
                    if present is not _MISSING:
                        return {"value": present}
                return {"value": spec.producer(ctx, self)}

            registry.register(str(provider.target), build, builder_id=f"field:{provider.target.logical_resource_id}")
        for (document, parts), target in self._composites.items():
            def build_object(ctx, doc=document, path=parts):
                return {"value": self.compose(ctx, doc, path=format_json_pointer(path))}
            registry.register(str(target), build_object, builder_id=f"object:{target.logical_resource_id}", dependency_type="aggregate")

    def describe(self):
        """Expose logical path → internal target mapping for diagnostics."""
        return {
            "fields": [{"document": doc, "path": format_json_pointer(path),
                        "source": str(spec.source) if isinstance(spec, _Input) else str(spec.target)}
                       for (doc, path), spec in self._providers.items()],
            "objects": [{"document": doc, "path": format_json_pointer(path), "target": str(target)}
                        for (doc, path), target in self._composites.items()],
        }

    @staticmethod
    def object_target(document, path):
        """Stable aggregate ID, also usable for explicit compatibility aliases."""
        key = (FieldPlan._document(document), parse_json_pointer(path))
        digest = hashlib.sha256(json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return ResourceRef.from_resource_id("field_objects.o_" + digest)
