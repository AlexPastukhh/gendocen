"""Persisted dependency receipts, baselines, diffs, graph and runtime state.

P3 intentionally stops at structural invalidation. It records what a target was
validated/built against and detects changes. Semantic truth remains a human/AI
review concern handled by later phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
import re
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .builders import BuildEngine, BuilderRegistry, DependencyRead, DerivedObject
from .objects import FrozenMapping, RawObject, thaw
from .project import ProjectRoots, is_within
from .refs import RefError, ResourceRef
from .resources import ResourceCatalog, ResourceError
from .versions import PERSISTED_STATE_SCHEMA_VERSION
from .hardening import HardeningError, append_text as _hardened_append_text, atomic_write_text as _hardened_atomic_write_text


class DependencyError(RuntimeError):
    """Base dependency runtime failure."""


class BaselineError(DependencyError):
    pass


class ReceiptError(DependencyError):
    pass


class StateError(DependencyError):
    pass


class ComparatorError(DependencyError):
    pass


_CANONICAL_STATUSES = frozenset({"valid", "stale", "review_required", "build_required", "invalid"})
_REBUILDABLE_TYPES = frozenset({"copy_reference", "compute", "aggregate"})
_REVIEW_TYPES = frozenset({"semantic_review", "compatibility"})
_VALID_DEPENDENCY_TYPES = _REBUILDABLE_TYPES | _REVIEW_TYPES | {"validity"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_timestamp(value: str, *, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise DependencyError(f"{label} must be a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DependencyError(f"{label} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise DependencyError(f"{label} must include timezone information")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_digest_bytes(_canonical_json(value))}"


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _safe_dependency_root(roots: ProjectRoots) -> Path:
    docs = roots.documentation_root.resolve(strict=False)
    root = (roots.documentation_root / roots.config.dependency_dir).resolve(strict=False)
    if not is_within(root, docs):
        raise StateError("dependency runtime directory escapes documentation root")
    configured = roots.documentation_root / roots.config.dependency_dir
    if configured.is_symlink():
        raise StateError("dependency runtime directory must not be a symlink")
    return root


def _safe_runtime_path(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve(strict=False)
    if not is_within(resolved, root.resolve(strict=False)):
        raise StateError("dependency runtime path escapes dependency root")
    # Refuse pre-existing symlink components under runtime ownership.
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise StateError(f"dependency runtime path contains symlink: {current}")
    return candidate


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise StateError(f"refusing to write through symlink: {path}")
    try:
        _hardened_atomic_write_text(path, text)
    except HardeningError as exc:
        raise StateError(str(exc)) from exc


def _granularity(ref: ResourceRef) -> str:
    if ref.scheme == "file":
        return "whole_file"
    if ref.scheme == "resource":
        return "field" if ref.pointer_parts else "resource"
    raise DependencyError(f"unsupported dependency ref scheme: {ref.scheme}")


@dataclass(frozen=True, slots=True)
class DiffResult:
    comparator: str
    changed: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"comparator": self.comparator, "changed": self.changed, "details": self.details}


class ComparatorRegistry:
    """Built-in comparator registry for v0.1."""

    REQUIRED = ("exact", "json_structured", "sequence", "set", "text_unified")

    def __init__(self) -> None:
        self._comparators = {
            "exact": self._exact,
            "json_structured": self._json_structured,
            "sequence": self._sequence,
            "set": self._set,
            "text_unified": self._text_unified,
        }

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._comparators))

    def validate_id(self, comparator: str) -> str:
        if comparator not in self._comparators:
            raise ComparatorError(f"unknown comparator {comparator!r}; expected one of {sorted(self._comparators)}")
        return comparator

    def compare(self, comparator: str, old: Any, new: Any) -> DiffResult:
        self.validate_id(comparator)
        return self._comparators[comparator](old, new)

    @staticmethod
    def _exact(old: Any, new: Any) -> DiffResult:
        changed = thaw(old) != thaw(new)
        return DiffResult("exact", changed, {"old": thaw(old), "new": thaw(new)} if changed else {})

    @staticmethod
    def _structured_changes(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
        old = thaw(old)
        new = thaw(new)
        if isinstance(old, dict) and isinstance(new, dict):
            changes: list[dict[str, Any]] = []
            for key in sorted(set(old) | set(new)):
                child = path + "/" + key.replace("~", "~0").replace("/", "~1")
                if key not in old:
                    changes.append({"path": child, "change": "added", "new": new[key]})
                elif key not in new:
                    changes.append({"path": child, "change": "removed", "old": old[key]})
                else:
                    changes.extend(ComparatorRegistry._structured_changes(old[key], new[key], child))
            return changes
        if isinstance(old, list) and isinstance(new, list):
            if old == new:
                return []
            return [{"path": path or "/", "change": "replaced", "old": old, "new": new}]
        if old == new:
            return []
        return [{"path": path or "/", "change": "replaced", "old": old, "new": new}]

    @classmethod
    def _json_structured(cls, old: Any, new: Any) -> DiffResult:
        changes = cls._structured_changes(old, new)
        return DiffResult("json_structured", bool(changes), {"changes": changes} if changes else {})

    @staticmethod
    def _sequence(old: Any, new: Any) -> DiffResult:
        old_list = list(thaw(old)) if isinstance(thaw(old), (list, tuple)) else None
        new_list = list(thaw(new)) if isinstance(thaw(new), (list, tuple)) else None
        if old_list is None or new_list is None:
            raise ComparatorError("sequence comparator requires array values")
        old_tokens = [_canonical_json(v).decode("utf-8") for v in old_list]
        new_tokens = [_canonical_json(v).decode("utf-8") for v in new_list]
        matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
        ops: list[dict[str, Any]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            ops.append({
                "op": tag,
                "old_range": [i1, i2],
                "new_range": [j1, j2],
                "old": old_list[i1:i2],
                "new": new_list[j1:j2],
            })
        return DiffResult("sequence", bool(ops), {"operations": ops} if ops else {})

    @staticmethod
    def _set(old: Any, new: Any) -> DiffResult:
        old_values = list(thaw(old)) if isinstance(thaw(old), (list, tuple)) else None
        new_values = list(thaw(new)) if isinstance(thaw(new), (list, tuple)) else None
        if old_values is None or new_values is None:
            raise ComparatorError("set comparator requires array values")
        old_map = {_canonical_json(v).decode("utf-8"): v for v in old_values}
        new_map = {_canonical_json(v).decode("utf-8"): v for v in new_values}
        removed = [old_map[k] for k in sorted(set(old_map) - set(new_map))]
        added = [new_map[k] for k in sorted(set(new_map) - set(old_map))]
        changed = bool(removed or added)
        return DiffResult("set", changed, {"removed": removed, "added": added} if changed else {})

    @staticmethod
    def _text_unified(old: Any, new: Any) -> DiffResult:
        if not isinstance(old, str) or not isinstance(new, str):
            raise ComparatorError("text_unified comparator requires string values")
        old_n = _normalize_text(old)
        new_n = _normalize_text(new)
        if old_n == new_n:
            return DiffResult("text_unified", False, {})
        diff = "".join(difflib.unified_diff(
            old_n.splitlines(keepends=True),
            new_n.splitlines(keepends=True),
            fromfile="validated",
            tofile="current",
            lineterm="\n",
        ))
        return DiffResult("text_unified", True, {"unified_diff": diff, "old": old_n, "new": new_n})


@dataclass(frozen=True, slots=True)
class BaselineSnapshot:
    baseline_hash: str
    snapshot_ref: str
    kind: str
    value: Any


class BaselineStore:
    def __init__(self, roots: ProjectRoots) -> None:
        dep = _safe_dependency_root(roots)
        self.root = _safe_runtime_path(dep, "baselines")

    @staticmethod
    def _wrapper(value: Any, comparator: str) -> dict[str, Any]:
        if comparator == "text_unified":
            if not isinstance(value, str):
                raise BaselineError("text_unified baseline requires string value")
            return {"state_schema_version": PERSISTED_STATE_SCHEMA_VERSION, "format": "text_utf8_lf", "value": _normalize_text(value)}
        return {"state_schema_version": PERSISTED_STATE_SCHEMA_VERSION, "format": "canonical_json", "value": thaw(value)}

    def put(self, value: Any, *, comparator: str) -> BaselineSnapshot:
        wrapper = self._wrapper(value, comparator)
        data = _canonical_json(wrapper)
        digest = _digest_bytes(data)
        path = _safe_runtime_path(self.root, f"sha256-{digest}.json")
        if path.exists():
            existing = path.read_bytes().rstrip(b"\n")
            if path.is_symlink() or existing != data:
                raise BaselineError(f"content-addressed baseline collision/corruption: {path.name}")
        else:
            _atomic_write_text(path, data.decode("utf-8") + "\n")
        return BaselineSnapshot(
            baseline_hash=f"sha256:{digest}",
            snapshot_ref=f"baseline://sha256/{digest}",
            kind=wrapper["format"],
            value=wrapper["value"],
        )

    def load(self, snapshot_ref: str, *, expected_hash: str | None = None) -> BaselineSnapshot:
        prefix = "baseline://sha256/"
        if not isinstance(snapshot_ref, str) or not snapshot_ref.startswith(prefix):
            raise BaselineError(f"invalid baseline snapshot ref: {snapshot_ref!r}")
        digest = snapshot_ref[len(prefix):]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise BaselineError(f"invalid baseline digest: {digest!r}")
        path = _safe_runtime_path(self.root, f"sha256-{digest}.json")
        if not path.is_file() or path.is_symlink():
            raise BaselineError(f"baseline snapshot missing: {snapshot_ref}")
        raw = path.read_bytes()
        canonical = raw.rstrip(b"\n")
        actual = _digest_bytes(canonical)
        if actual != digest:
            raise BaselineError(f"baseline content hash mismatch: {snapshot_ref}")
        try:
            wrapper = json.loads(canonical)
        except json.JSONDecodeError as exc:
            raise BaselineError(f"invalid baseline JSON: {snapshot_ref}: {exc}") from exc
        if (
            not isinstance(wrapper, dict)
            or wrapper.get("state_schema_version") != PERSISTED_STATE_SCHEMA_VERSION
            or wrapper.get("format") not in {"canonical_json", "text_utf8_lf"}
            or "value" not in wrapper
        ):
            raise BaselineError(f"invalid or unsupported baseline wrapper: {snapshot_ref}")
        baseline_hash = f"sha256:{digest}"
        if expected_hash is not None and expected_hash != baseline_hash:
            raise BaselineError(f"baseline hash/ref mismatch: expected {expected_hash}, got {baseline_hash}")
        return BaselineSnapshot(baseline_hash, snapshot_ref, wrapper["format"], wrapper["value"])


@dataclass(frozen=True, slots=True)
class DependencyEntry:
    source: str
    granularity: str
    comparator: str
    baseline_hash: str
    snapshot_ref: str
    observed_version: str
    source_kind: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "granularity": self.granularity,
            "comparator": self.comparator,
            "baseline_hash": self.baseline_hash,
            "snapshot_ref": self.snapshot_ref,
            "observed_version": self.observed_version,
            "source_kind": self.source_kind,
        }


@dataclass(frozen=True, slots=True)
class DependencyReceipt:
    receipt_id: str
    target: str
    validated_at: str
    dependency_type: str
    dependencies: tuple[DependencyEntry, ...]
    builder_id: str | None = None
    builder_revision: str | None = None
    output_digest: str | None = None
    audit_complete: bool = True
    target_revision: str | None = None
    semantic_rule_id: str | None = None
    semantic_rule_revision: str | None = None

    def stable_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
            "target": self.target,
            "dependency_type": self.dependency_type,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "audit_complete": self.audit_complete,
        }
        optional = {
            "builder_id": self.builder_id,
            "builder_revision": self.builder_revision,
            "output_digest": self.output_digest,
            "target_revision": self.target_revision,
            "semantic_rule_id": self.semantic_rule_id,
            "semantic_rule_revision": self.semantic_rule_revision,
        }
        payload.update({k: v for k, v in optional.items() if v is not None})
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload = self.stable_payload()
        payload.update({"receipt_id": self.receipt_id, "validated_at": self.validated_at})
        receipt_hash = "sha256:" + _digest_bytes(_canonical_json(payload))
        payload["receipt_hash"] = receipt_hash
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DependencyReceipt":
        try:
            if not isinstance(data, Mapping):
                raise ReceiptError("dependency receipt must be an object")
            if data.get("state_schema_version") != PERSISTED_STATE_SCHEMA_VERSION:
                raise ReceiptError(
                    f"unsupported receipt state_schema_version: {data.get('state_schema_version')!r}"
                )
            for key in ("receipt_id", "target", "validated_at", "dependency_type"):
                if not isinstance(data.get(key), str) or not data.get(key):
                    raise ReceiptError(f"receipt {key} must be a non-empty string")
            if "audit_complete" not in data or not isinstance(data.get("audit_complete"), bool):
                raise ReceiptError("receipt audit_complete must be a boolean")
            raw_dependencies = data.get("dependencies")
            if not isinstance(raw_dependencies, list):
                raise ReceiptError("receipt dependencies must be an array")
            for key in ("builder_id", "builder_revision", "output_digest", "target_revision", "semantic_rule_id", "semantic_rule_revision"):
                if key in data and (not isinstance(data[key], str) or not data[key]):
                    raise ReceiptError(f"receipt {key} must be a non-empty string when present")
            _validate_timestamp(data["validated_at"], label="receipt validated_at")
            dep_type = data["dependency_type"]
            if dep_type not in _VALID_DEPENDENCY_TYPES:
                raise ReceiptError(f"invalid dependency_type: {dep_type}")
            deps_list: list[DependencyEntry] = []
            for x in raw_dependencies:
                if not isinstance(x, Mapping):
                    raise ReceiptError("dependency entry must be an object")
                required = ("source", "granularity", "comparator", "baseline_hash", "snapshot_ref", "observed_version", "source_kind")
                for key in required:
                    if not isinstance(x.get(key), str) or not x.get(key):
                        raise ReceiptError(f"dependency {key} must be a non-empty string")
                if x["source_kind"] not in {"raw", "derived", "file"}:
                    raise ReceiptError(f"invalid dependency source_kind: {x['source_kind']}")
                deps_list.append(DependencyEntry(
                    source=x["source"],
                    granularity=x["granularity"],
                    comparator=x["comparator"],
                    baseline_hash=x["baseline_hash"],
                    snapshot_ref=x["snapshot_ref"],
                    observed_version=x["observed_version"],
                    source_kind=x["source_kind"],
                ))
            deps = tuple(deps_list)
            receipt = cls(
                receipt_id=data["receipt_id"],
                target=data["target"],
                validated_at=data["validated_at"],
                dependency_type=dep_type,
                dependencies=deps,
                builder_id=data.get("builder_id"),
                builder_revision=data.get("builder_revision"),
                output_digest=data.get("output_digest"),
                audit_complete=data["audit_complete"],
                target_revision=data.get("target_revision"),
                semantic_rule_id=data.get("semantic_rule_id"),
                semantic_rule_revision=data.get("semantic_rule_revision"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReceiptError(f"invalid dependency receipt: {exc}") from exc
        if (receipt.semantic_rule_id is None) != (receipt.semantic_rule_revision is None):
            raise ReceiptError("semantic_rule_id and semantic_rule_revision must be present together")
        try:
            target_ref = ResourceRef.parse(receipt.target)
            if str(target_ref) != receipt.target:
                raise ReceiptError(f"non-canonical target ref in receipt: {receipt.target}")
            seen_sources: set[str] = set()
            for dep in receipt.dependencies:
                source_ref = ResourceRef.parse(dep.source)
                if str(source_ref) != dep.source:
                    raise ReceiptError(f"non-canonical source ref in receipt: {dep.source}")
                if dep.source in seen_sources:
                    raise ReceiptError(f"duplicate dependency source in receipt: {dep.source}")
                seen_sources.add(dep.source)
                if dep.granularity != _granularity(source_ref):
                    raise ReceiptError(
                        f"dependency granularity mismatch for {dep.source}: {dep.granularity} vs {_granularity(source_ref)}"
                    )
                if dep.comparator not in ComparatorRegistry.REQUIRED:
                    raise ReceiptError(f"unknown comparator in receipt: {dep.comparator}")
        except RefError as exc:
            raise ReceiptError(f"invalid ref in receipt: {exc}") from exc
        expected = _stable_id("receipt", receipt.stable_payload())
        if receipt.receipt_id != expected:
            raise ReceiptError(f"receipt id/content mismatch: {receipt.receipt_id} != {expected}")
        stored_hash = data.get("receipt_hash")
        hash_payload = receipt.stable_payload()
        hash_payload.update({"receipt_id": receipt.receipt_id, "validated_at": receipt.validated_at})
        expected_hash = "sha256:" + _digest_bytes(_canonical_json(hash_payload))
        if stored_hash != expected_hash:
            raise ReceiptError(f"receipt hash mismatch: {stored_hash!r} != {expected_hash}")
        return receipt


class ReceiptStore:
    def __init__(self, roots: ProjectRoots) -> None:
        dep = _safe_dependency_root(roots)
        self.root = _safe_runtime_path(dep, "receipts")

    def put(self, receipt: DependencyReceipt) -> DependencyReceipt:
        path = _safe_runtime_path(self.root, f"{receipt.receipt_id}.json")
        if path.exists():
            existing = self.load(receipt.receipt_id)
            if existing.stable_payload() != receipt.stable_payload():
                raise ReceiptError(f"receipt id collision: {receipt.receipt_id}")
            return existing
        text = json.dumps(receipt.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        _atomic_write_text(path, text)
        return receipt

    def load(self, receipt_id: str) -> DependencyReceipt:
        if not isinstance(receipt_id, str) or not receipt_id.startswith("receipt-"):
            raise ReceiptError(f"invalid receipt id: {receipt_id!r}")
        path = _safe_runtime_path(self.root, f"{receipt_id}.json")
        if not path.is_file() or path.is_symlink():
            raise ReceiptError(f"receipt missing: {receipt_id}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReceiptError(f"invalid receipt JSON {receipt_id}: {exc}") from exc
        return DependencyReceipt.from_dict(data)

    def all(self) -> tuple[DependencyReceipt, ...]:
        receipts: list[DependencyReceipt] = []
        for path in sorted(self.root.glob("receipt-*.json")):
            receipts.append(self.load(path.stem))
        return tuple(receipts)

    def latest_by_target(self) -> dict[str, DependencyReceipt]:
        latest: dict[str, DependencyReceipt] = {}
        for receipt in self.all():
            current = latest.get(receipt.target)
            if current is None or (receipt.validated_at, receipt.receipt_id) > (current.validated_at, current.receipt_id):
                latest[receipt.target] = receipt
        return latest


@dataclass(frozen=True, slots=True)
class DependencyStateEntry:
    status: str
    changed_dependencies: tuple[str, ...]
    last_receipt_id: str
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "changed_dependencies": list(self.changed_dependencies),
            "last_receipt_id": self.last_receipt_id,
            "reason_codes": list(self.reason_codes),
        }


class StateStore:
    def __init__(self, roots: ProjectRoots) -> None:
        dep = _safe_dependency_root(roots)
        self.path = _safe_runtime_path(dep, "state", "dependency_state.json")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
                "generated_at": None,
                "state_revision": 0,
                "targets": {},
            }
        if self.path.is_symlink():
            raise StateError("dependency_state.json must not be a symlink")
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StateError(f"invalid dependency state JSON: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("targets"), dict):
            raise StateError("dependency state must contain object targets")
        if data.get("state_schema_version") != PERSISTED_STATE_SCHEMA_VERSION:
            raise StateError(
                f"unsupported dependency state schema version: {data.get('state_schema_version')!r}"
            )
        for target, entry in data["targets"].items():
            try:
                ref = ResourceRef.parse(target)
            except RefError as exc:
                raise StateError(f"invalid target ref in dependency state: {target}: {exc}") from exc
            if str(ref) != target:
                raise StateError(f"non-canonical target ref in dependency state: {target}")
            if not isinstance(entry, dict) or entry.get("status") not in _CANONICAL_STATUSES:
                raise StateError(f"invalid state entry for {target}")
            if not isinstance(entry.get("last_receipt_id"), str):
                raise StateError(f"state entry missing last_receipt_id for {target}")
            for key in ("changed_dependencies", "reason_codes"):
                values = entry.get(key)
                if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                    raise StateError(f"state entry {key} must be an array of strings for {target}")
        generated_at = data.get("generated_at")
        if generated_at is not None:
            _validate_timestamp(generated_at, label="dependency state generated_at")
        state_revision = data.get("state_revision", 0)
        if not isinstance(state_revision, int) or isinstance(state_revision, bool) or state_revision < 0:
            raise StateError("dependency state state_revision must be a non-negative integer")
        data["state_revision"] = state_revision
        return data

    def write_targets(self, targets: Mapping[str, Mapping[str, Any]], *, state_revision: int) -> dict[str, Any]:
        if not isinstance(state_revision, int) or isinstance(state_revision, bool) or state_revision < 0:
            raise StateError("state_revision must be a non-negative integer")
        payload = {
            "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "state_revision": state_revision,
            "targets": {k: dict(targets[k]) for k in sorted(targets)},
        }
        _atomic_write_text(self.path, json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        return payload

    def set_entry(self, target: str, entry: DependencyStateEntry) -> tuple[dict[str, Any], bool]:
        state = self.load()
        targets = dict(state.get("targets", {}))
        new = entry.to_dict()
        changed = targets.get(target) != new
        if changed:
            targets[target] = new
            state = self.write_targets(
                targets,
                state_revision=int(state.get("state_revision", 0)) + 1,
            )
        return state, changed


class EventStore:
    def __init__(self, roots: ProjectRoots) -> None:
        dep = _safe_dependency_root(roots)
        self.path = _safe_runtime_path(dep, "events", "dependency_events.jsonl")

    def all(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        if self.path.is_symlink():
            raise StateError("dependency_events.jsonl must not be a symlink")
        events: list[dict[str, Any]] = []
        ids: dict[str, dict[str, Any]] = {}
        for lineno, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StateError(f"invalid event JSON at line {lineno}: {exc}") from exc
            if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
                raise StateError(f"invalid dependency event at line {lineno}")
            for key in ("event_type", "target", "receipt_id", "recorded_at"):
                if not isinstance(event.get(key), str) or not event.get(key):
                    raise StateError(f"invalid dependency event {key} at line {lineno}")
            for key in ("changed_dependencies", "reason_codes"):
                values = event.get(key)
                if not isinstance(values, list) or not all(isinstance(x, str) for x in values):
                    raise StateError(f"dependency event {key} must be an array of strings at line {lineno}")
            state_revision = event.get("state_revision")
            if state_revision is not None and (
                not isinstance(state_revision, int)
                or isinstance(state_revision, bool)
                or state_revision < 1
            ):
                raise StateError(f"dependency event state_revision must be a positive integer at line {lineno}")
            if event.get("status") not in _CANONICAL_STATUSES:
                raise StateError(f"invalid dependency event status at line {lineno}")
            try:
                target_ref = ResourceRef.parse(event["target"])
            except RefError as exc:
                raise StateError(f"invalid dependency event target at line {lineno}: {exc}") from exc
            if str(target_ref) != event["target"]:
                raise StateError(f"non-canonical dependency event target at line {lineno}: {event['target']}")
            _validate_timestamp(event["recorded_at"], label=f"dependency event line {lineno} recorded_at")
            review = event.get("review")
            if review is not None:
                if not isinstance(review, dict):
                    raise StateError(f"dependency event review must be an object at line {lineno}")
                required_review = ("context_id", "decision", "reason", "actor_kind", "evidence", "rule_id", "rule_revision")
                allowed_review = set(required_review) | {"actor_label", "prior_receipt_id"}
                unknown_review = sorted(set(review) - allowed_review)
                if unknown_review:
                    raise StateError(f"dependency event review has unknown keys at line {lineno}: {unknown_review}")
                for key in required_review:
                    if key not in review:
                        raise StateError(f"dependency event review missing {key} at line {lineno}")
                for key in ("context_id", "decision", "reason", "actor_kind", "rule_id", "rule_revision"):
                    if not isinstance(review.get(key), str) or not review.get(key):
                        raise StateError(f"dependency event review {key} must be a non-empty string at line {lineno}")
                if not re.fullmatch(r"reviewctx-[0-9a-f]{64}", review["context_id"]):
                    raise StateError(f"invalid semantic review context_id at line {lineno}")
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", review["rule_revision"]):
                    raise StateError(f"invalid semantic review rule_revision at line {lineno}")
                if review["decision"] not in {"still-valid", "updated"}:
                    raise StateError(f"invalid semantic review decision at line {lineno}")
                if review["actor_kind"] not in {"human", "ai", "ci", "unknown"}:
                    raise StateError(f"invalid semantic review actor_kind at line {lineno}")
                if not isinstance(review.get("evidence"), list) or not all(isinstance(x, str) and x for x in review["evidence"]):
                    raise StateError(f"dependency event review evidence must be non-empty strings at line {lineno}")
                if "actor_label" in review and (not isinstance(review["actor_label"], str) or not review["actor_label"]):
                    raise StateError(f"dependency event review actor_label must be non-empty when present at line {lineno}")
                if "prior_receipt_id" in review and review["prior_receipt_id"] is not None and (not isinstance(review["prior_receipt_id"], str) or not review["prior_receipt_id"]):
                    raise StateError(f"dependency event review prior_receipt_id must be string/null at line {lineno}")
            stable = {
                "event_type": event.get("event_type"),
                "target": event.get("target"),
                "receipt_id": event.get("receipt_id"),
                "status": event.get("status"),
                "changed_dependencies": event.get("changed_dependencies", []),
                "reason_codes": event.get("reason_codes", []),
            }
            if state_revision is not None:
                stable["state_revision"] = state_revision
            if review is not None:
                stable["review"] = review
            expected_event_id = _stable_id("event", stable)
            if event["event_id"] != expected_event_id:
                raise StateError(
                    f"dependency event id/content mismatch at line {lineno}: {event['event_id']} != {expected_event_id}"
                )
            existing = ids.get(event["event_id"])
            if existing is not None and existing != event:
                raise StateError(f"conflicting duplicate event_id: {event['event_id']}")
            ids[event["event_id"]] = event
            events.append(event)
        return tuple(events)

    def append(self, *, event_type: str, target: str, receipt_id: str, status: str, changed_dependencies: Sequence[str], reason_codes: Sequence[str], state_revision: int, review: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(state_revision, int) or isinstance(state_revision, bool) or state_revision < 1:
            raise StateError("event state_revision must be a positive integer")
        stable: dict[str, Any] = {
            "event_type": event_type,
            "target": target,
            "receipt_id": receipt_id,
            "status": status,
            "changed_dependencies": sorted(set(changed_dependencies)),
            "reason_codes": sorted(set(reason_codes)),
            "state_revision": state_revision,
        }
        if review is not None:
            stable["review"] = dict(review)
        event_id = _stable_id("event", stable)
        existing = {event["event_id"]: event for event in self.all()}
        if event_id in existing:
            return existing[event_id]
        event = {"event_id": event_id, "recorded_at": _utc_now(), **stable}
        line = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        if self.path.exists() and self.path.is_symlink():
            raise StateError("dependency_events.jsonl must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise StateError("dependency events directory must not be a symlink")
        try:
            _hardened_append_text(self.path, line)
        except HardeningError as exc:
            raise StateError(str(exc)) from exc
        return event

    def for_target(self, target: str) -> tuple[dict[str, Any], ...]:
        return tuple(event for event in self.all() if event.get("target") == target)


@dataclass(frozen=True, slots=True)
class ExplicitDependency:
    source: ResourceRef
    comparator: str = "exact"

    @classmethod
    def create(cls, source: ResourceRef | str, *, comparator: str = "exact") -> "ExplicitDependency":
        ref = ResourceRef.parse(source) if isinstance(source, str) else source
        return cls(ref, comparator)


class DependencyResolver:
    def __init__(self, catalog: ResourceCatalog, registry: BuilderRegistry | None = None) -> None:
        self.catalog = catalog
        self.registry = registry or BuilderRegistry()

    @staticmethod
    def _whole(ref: ResourceRef) -> ResourceRef:
        if ref.scheme != "resource":
            return ref
        return ResourceRef(
            scheme="resource",
            namespace=ref.namespace,
            resource_id=ref.resource_id,
            pointer_parts=(),
        )

    def _is_derived(self, ref: ResourceRef) -> bool:
        return ref.scheme == "resource" and self.registry.has_target(self._whole(ref))

    def value_and_version(self, ref: ResourceRef | str) -> tuple[Any, str, str]:
        resource_ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if self._is_derived(resource_ref):
            obj = BuildEngine(self.catalog, self.registry).build(self._whole(resource_ref))
            if resource_ref.pointer_parts:
                return obj.read(resource_ref), obj.version_for(resource_ref), "derived"
            return obj.data, obj.version, "derived"
        value = self.catalog.resolve(resource_ref)
        if isinstance(value, RawObject):
            value = value.data
        return value, self.catalog.version(resource_ref), "file" if resource_ref.scheme == "file" else "raw"


class DependencyGraph:
    def __init__(self, receipts: Iterable[DependencyReceipt]) -> None:
        self.receipts = tuple(receipts)
        self.upstream: dict[str, tuple[str, ...]] = {}
        reverse: dict[str, set[str]] = {}
        for receipt in self.receipts:
            sources = tuple(sorted(dep.source for dep in receipt.dependencies))
            self.upstream[receipt.target] = sources
            for source in sources:
                reverse.setdefault(source, set()).add(receipt.target)
        self.reverse = {source: tuple(sorted(targets)) for source, targets in sorted(reverse.items())}

    def affected_by(self, source: ResourceRef | str) -> tuple[str, ...]:
        ref = str(ResourceRef.parse(source) if isinstance(source, str) else source)
        return self.reverse.get(ref, ())

    def to_dict(self, target: str | None = None) -> dict[str, Any]:
        if target is not None:
            return {
                "target": target,
                "upstream": list(self.upstream.get(target, ())),
                "downstream": list(self.reverse.get(target, ())),
            }
        edges = [
            {"target": target_ref, "source": source}
            for target_ref in sorted(self.upstream)
            for source in self.upstream[target_ref]
        ]
        return {"edges": edges, "edge_count": len(edges), "target_count": len(self.upstream)}


class DependencyRuntime:
    """P3 runtime: persist receipts/baselines, detect changes, explain state."""

    def __init__(self, roots: ProjectRoots, catalog: ResourceCatalog | None = None, registry: BuilderRegistry | None = None, *, semantic_rule_revisions: Mapping[str, tuple[str, str]] | None = None) -> None:
        self.roots = roots
        self.catalog = catalog
        self.registry = registry or BuilderRegistry()
        self.resolver = DependencyResolver(catalog, self.registry) if catalog is not None else None
        self.semantic_rule_revisions = dict(semantic_rule_revisions or {})
        self.builder_load_error: str | None = None
        self.comparators = ComparatorRegistry()
        self.baselines = BaselineStore(roots)
        self.receipts = ReceiptStore(roots)
        self.state = StateStore(roots)
        self.events = EventStore(roots)

    def _require_resolver(self) -> DependencyResolver:
        if self.resolver is None or self.catalog is None:
            raise DependencyError("current resource catalog is required for this dependency operation")
        return self.resolver

    def _entry_from_snapshot(self, source: ResourceRef, value: Any, version: str, source_kind: str, comparator: str) -> DependencyEntry:
        comparator = self.comparators.validate_id(comparator)
        snap = self.baselines.put(value, comparator=comparator)
        return DependencyEntry(
            source=str(source),
            granularity=_granularity(source),
            comparator=comparator,
            baseline_hash=snap.baseline_hash,
            snapshot_ref=snap.snapshot_ref,
            observed_version=version,
            source_kind=source_kind,
        )

    def _receipt(self, *, target: str, dependency_type: str, dependencies: Sequence[DependencyEntry], builder_id: str | None = None, builder_revision: str | None = None, output_digest: str | None = None, audit_complete: bool = True, target_revision: str | None = None, semantic_rule_id: str | None = None, semantic_rule_revision: str | None = None) -> DependencyReceipt:
        if dependency_type not in _VALID_DEPENDENCY_TYPES:
            raise ReceiptError(f"invalid dependency_type: {dependency_type}")
        sources = [dep.source for dep in dependencies]
        if len(sources) != len(set(sources)):
            raise ReceiptError("duplicate dependency sources are not allowed in one receipt")
        stable = {
            "state_schema_version": PERSISTED_STATE_SCHEMA_VERSION,
            "target": target,
            "dependency_type": dependency_type,
            "dependencies": [dep.to_dict() for dep in sorted(dependencies, key=lambda d: d.source)],
            "audit_complete": audit_complete,
        }
        optional = {
            "builder_id": builder_id,
            "builder_revision": builder_revision,
            "output_digest": output_digest,
            "target_revision": target_revision,
            "semantic_rule_id": semantic_rule_id,
            "semantic_rule_revision": semantic_rule_revision,
        }
        stable.update({k: v for k, v in optional.items() if v is not None})
        receipt_id = _stable_id("receipt", stable)
        return DependencyReceipt(
            receipt_id=receipt_id,
            target=target,
            validated_at=_utc_now(),
            dependency_type=dependency_type,
            dependencies=tuple(sorted(dependencies, key=lambda d: d.source)),
            builder_id=builder_id,
            builder_revision=builder_revision,
            output_digest=output_digest,
            audit_complete=audit_complete,
            target_revision=target_revision,
            semantic_rule_id=semantic_rule_id,
            semantic_rule_revision=semantic_rule_revision,
        )

    def _mark_valid(self, receipt: DependencyReceipt, *, event_type: str) -> DependencyReceipt:
        stored = self.receipts.put(receipt)
        status = "valid" if stored.audit_complete else "invalid"
        reasons = () if stored.audit_complete else ("audit_incomplete",)
        entry = DependencyStateEntry(status, (), stored.receipt_id, reasons)
        state, state_changed = self.state.set_entry(stored.target, entry)
        if state_changed:
            self.events.append(
                event_type=event_type if stored.audit_complete else event_type + "_audit_incomplete",
                target=stored.target,
                receipt_id=stored.receipt_id,
                status=status,
                changed_dependencies=(),
                reason_codes=reasons,
                state_revision=state["state_revision"],
            )
        return stored

    def record_build(self, result: DerivedObject) -> DependencyReceipt:
        entries: list[DependencyEntry] = []
        for dep in result.provenance.dependencies:
            snapshot = dep.snapshot_value
            entries.append(self._entry_from_snapshot(dep.ref, snapshot, dep.version, dep.source_kind, dep.comparator))
        receipt = self._receipt(
            target=str(result.ref),
            dependency_type=result.provenance.dependency_type,
            dependencies=entries,
            builder_id=result.provenance.builder_id,
            builder_revision=result.provenance.builder_revision,
            output_digest=result.provenance.output_digest,
            audit_complete=result.provenance.audit_complete,
        )
        return self._mark_valid(receipt, event_type="build_recorded")

    def _validate_target_ref(self, target_ref: ResourceRef) -> None:
        self._require_resolver()
        assert self.catalog is not None
        if target_ref.scheme == "file":
            self.catalog.resolve(target_ref)
            return
        if target_ref.scheme == "resource":
            whole = ResourceRef(
                scheme="resource",
                namespace=target_ref.namespace,
                resource_id=target_ref.resource_id,
                pointer_parts=(),
            )
            if self.registry.has_target(whole):
                return
            self.catalog.resolve(whole)
            return
        raise ReceiptError(f"unsupported target ref: {target_ref}")

    def capture_explicit_receipt(self, target: ResourceRef | str, dependencies: Sequence[ExplicitDependency | tuple[ResourceRef | str, str] | ResourceRef | str], *, dependency_type: str = "semantic_review", target_revision: str | None = None, semantic_rule_id: str | None = None, semantic_rule_revision: str | None = None) -> DependencyReceipt:
        target_ref = ResourceRef.parse(target) if isinstance(target, str) else target
        self._validate_target_ref(target_ref)
        if target_revision is None:
            # Explicit review/validation receipts describe both the upstream
            # dependency baseline and the exact target revision that was
            # reviewed. Otherwise editing the target itself could leave an old
            # validation receipt looking current.
            _, target_revision, _ = self._require_resolver().value_and_version(target_ref)
        if (semantic_rule_id is None) != (semantic_rule_revision is None):
            raise ReceiptError("semantic_rule_id and semantic_rule_revision must be provided together")
        entries: list[DependencyEntry] = []
        for item in dependencies:
            if isinstance(item, ExplicitDependency):
                dep = item
            elif isinstance(item, tuple):
                dep = ExplicitDependency.create(item[0], comparator=item[1])
            else:
                dep = ExplicitDependency.create(item)
            value, version, source_kind = self._require_resolver().value_and_version(dep.source)
            entries.append(self._entry_from_snapshot(dep.source, value, version, source_kind, dep.comparator))
        receipt = self._receipt(
            target=str(target_ref),
            dependency_type=dependency_type,
            dependencies=entries,
            target_revision=target_revision,
            semantic_rule_id=semantic_rule_id,
            semantic_rule_revision=semantic_rule_revision,
        )
        return self.receipts.put(receipt)

    def record_explicit(self, target: ResourceRef | str, dependencies: Sequence[ExplicitDependency | tuple[ResourceRef | str, str] | ResourceRef | str], *, dependency_type: str = "semantic_review", target_revision: str | None = None) -> DependencyReceipt:
        receipt = self.capture_explicit_receipt(
            target,
            dependencies,
            dependency_type=dependency_type,
            target_revision=target_revision,
        )
        return self._mark_valid(receipt, event_type="validation_recorded")

    @staticmethod
    def _changed_status(dep_type: str) -> str:
        if dep_type in _REBUILDABLE_TYPES:
            return "build_required"
        if dep_type in _REVIEW_TYPES:
            return "review_required"
        if dep_type == "validity":
            return "stale"
        return "invalid"

    def _receipt_for_target(self, target: ResourceRef | str) -> DependencyReceipt:
        target_s = str(ResourceRef.parse(target) if isinstance(target, str) else target)
        state = self.state.load()
        entry = state.get("targets", {}).get(target_s)
        if entry and entry.get("last_receipt_id"):
            return self.receipts.load(entry["last_receipt_id"])
        latest = self.receipts.latest_by_target().get(target_s)
        if latest is None:
            raise ReceiptError(f"no dependency receipt for target: {target_s}")
        return latest

    def diff_receipt(self, receipt: DependencyReceipt) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        changed_sources: list[str] = []
        reason_codes: list[str] = []
        target_change: dict[str, Any] | None = None

        if receipt.target_revision is not None:
            try:
                _, current_target_revision, _ = self._require_resolver().value_and_version(receipt.target)
                target_changed = current_target_revision != receipt.target_revision
                target_change = {
                    "validated_revision": receipt.target_revision,
                    "current_revision": current_target_revision,
                    "changed": target_changed,
                }
                if target_changed:
                    reason_codes.append("target_changed_since_validation")
            except (DependencyError, ResourceError, RefError, KeyError, OSError) as exc:
                target_change = {
                    "validated_revision": receipt.target_revision,
                    "current_revision": None,
                    "changed": True,
                    "reason": "target_unavailable",
                    "error": str(exc),
                }
                reason_codes.append("target_unavailable")

        if receipt.semantic_rule_id is not None:
            current_rule = self.semantic_rule_revisions.get(receipt.target)
            rule_source = f"rule://{receipt.semantic_rule_id}"
            if current_rule is None:
                items.append({
                    "source": rule_source,
                    "kind": "semantic_rule_revision",
                    "changed": True,
                    "reason": "semantic_rule_unavailable",
                    "validated_rule_id": receipt.semantic_rule_id,
                    "validated_revision": receipt.semantic_rule_revision,
                    "current_rule_id": None,
                    "current_revision": None,
                })
                changed_sources.append(rule_source)
                reason_codes.append("semantic_rule_unavailable")
            else:
                current_rule_id, current_rule_revision = current_rule
                if current_rule_id != receipt.semantic_rule_id or current_rule_revision != receipt.semantic_rule_revision:
                    items.append({
                        "source": rule_source,
                        "kind": "semantic_rule_revision",
                        "changed": True,
                        "reason": "semantic_rule_revision_changed",
                        "validated_rule_id": receipt.semantic_rule_id,
                        "validated_revision": receipt.semantic_rule_revision,
                        "current_rule_id": current_rule_id,
                        "current_revision": current_rule_revision,
                    })
                    changed_sources.append(rule_source)
                    reason_codes.append("semantic_rule_revision_changed")

        if receipt.builder_id is not None:
            try:
                spec = self.registry.get(receipt.target)
            except Exception:
                spec = None
            if spec is None:
                items.append({
                    "source": f"builder://{receipt.builder_id}",
                    "kind": "builder_revision",
                    "changed": True,
                    "reason": "builder_unavailable",
                    "validated_revision": receipt.builder_revision,
                    "current_revision": None,
                    "error": self.builder_load_error,
                })
                changed_sources.append(f"builder://{receipt.builder_id}")
                reason_codes.append("builder_unavailable")
            elif spec.source_revision != receipt.builder_revision:
                items.append({
                    "source": f"builder://{receipt.builder_id}",
                    "kind": "builder_revision",
                    "changed": True,
                    "reason": "builder_revision_changed",
                    "validated_revision": receipt.builder_revision,
                    "current_revision": spec.source_revision,
                })
                changed_sources.append(f"builder://{receipt.builder_id}")
                reason_codes.append("builder_revision_changed")

        for dep in receipt.dependencies:
            baseline = self.baselines.load(dep.snapshot_ref, expected_hash=dep.baseline_hash)
            try:
                current, current_version, current_kind = self._require_resolver().value_and_version(dep.source)
                result = self.comparators.compare(dep.comparator, baseline.value, thaw(current))
                item = {
                    "source": dep.source,
                    "granularity": dep.granularity,
                    "source_kind": dep.source_kind,
                    "current_source_kind": current_kind,
                    "comparator": dep.comparator,
                    "validated_version": dep.observed_version,
                    "current_version": current_version,
                    "baseline_hash": dep.baseline_hash,
                    "snapshot_ref": dep.snapshot_ref,
                    **result.to_dict(),
                }
                if result.changed:
                    changed_sources.append(dep.source)
                    reason_codes.append("dependency_changed")
            except (DependencyError, ResourceError, RefError, KeyError, OSError) as exc:
                item = {
                    "source": dep.source,
                    "granularity": dep.granularity,
                    "comparator": dep.comparator,
                    "changed": True,
                    "error": str(exc),
                    "reason": "source_unavailable",
                    "baseline_hash": dep.baseline_hash,
                    "snapshot_ref": dep.snapshot_ref,
                }
                changed_sources.append(dep.source)
                reason_codes.append("source_unavailable")
            items.append(item)
        return {
            "target": receipt.target,
            "receipt_id": receipt.receipt_id,
            "dependency_type": receipt.dependency_type,
            "changed": bool(changed_sources) or bool(target_change and target_change.get("changed")),
            "changed_dependencies": sorted(set(changed_sources)),
            "reason_codes": sorted(set(reason_codes)),
            "target_revision": target_change,
            "dependencies": items,
        }

    def diff(self, target: ResourceRef | str) -> dict[str, Any]:
        return self.diff_receipt(self._receipt_for_target(target))

    def check(self, target: ResourceRef | str, *, dependency_type_override: str | None = None) -> dict[str, Any]:
        receipt = self._receipt_for_target(target)
        diff = self.diff_receipt(receipt)
        changed = diff["changed"]
        reasons = tuple(diff["reason_codes"])
        if dependency_type_override is not None and dependency_type_override not in _VALID_DEPENDENCY_TYPES:
            raise DependencyError(f"invalid dependency_type_override: {dependency_type_override}")
        effective_dependency_type = dependency_type_override or receipt.dependency_type
        if not receipt.audit_complete:
            status = "invalid"
            reasons = tuple(sorted(set(reasons) | {"audit_incomplete"}))
        elif any(reason in {"source_unavailable", "builder_unavailable", "target_unavailable", "semantic_rule_unavailable"} for reason in reasons):
            status = "invalid"
        else:
            status = self._changed_status(effective_dependency_type) if changed else "valid"
        changed_deps = tuple(diff["changed_dependencies"])
        entry = DependencyStateEntry(status, changed_deps, receipt.receipt_id, reasons)
        state, state_changed = self.state.set_entry(receipt.target, entry)
        if state_changed:
            self.events.append(
                event_type="dependency_state_changed" if changed else "dependency_state_confirmed",
                target=receipt.target,
                receipt_id=receipt.receipt_id,
                status=status,
                changed_dependencies=changed_deps,
                reason_codes=reasons,
                state_revision=state["state_revision"],
            )
        return {"target": receipt.target, "status": status, "state_changed": state_changed, "diff": diff}

    def _active_receipts(self) -> dict[str, DependencyReceipt]:
        """Return receipts currently selected by persisted state.

        Receipt IDs are content-stable and may be re-activated after a target
        temporarily validated against a different receipt. Therefore current
        selection must come from state, not from receipt creation timestamps.
        """
        state = self.state.load()
        active: dict[str, DependencyReceipt] = {}
        for target, entry in state.get("targets", {}).items():
            rid = entry.get("last_receipt_id")
            if isinstance(rid, str):
                active[target] = self.receipts.load(rid)
        # Fallback only for orphaned legacy receipt stores that predate state.
        for target, receipt in self.receipts.latest_by_target().items():
            active.setdefault(target, receipt)
        return active

    def active_receipts(self) -> dict[str, DependencyReceipt]:
        """Return the receipts currently selected by dependency state."""
        return dict(self._active_receipts())

    def check_all(self) -> dict[str, Any]:
        state = self.state.load()
        target_ids = set(state.get("targets", {})) | set(self._active_receipts())
        results = [self.check(target) for target in sorted(target_ids)]
        counts: dict[str, int] = {}
        for result in results:
            counts[result["status"]] = counts.get(result["status"], 0) + 1
        return {"results": results, "counts": dict(sorted(counts.items())), "checked": len(results)}

    def status(self) -> dict[str, Any]:
        state = self.state.load()
        counts: dict[str, int] = {}
        for entry in state.get("targets", {}).values():
            status = entry["status"]
            counts[status] = counts.get(status, 0) + 1
        return {"generated_at": state.get("generated_at"), "counts": dict(sorted(counts.items())), "targets": state.get("targets", {})}

    def explain(self, target: ResourceRef | str) -> dict[str, Any]:
        receipt = self._receipt_for_target(target)
        target_s = receipt.target
        state = self.state.load().get("targets", {}).get(target_s)
        return {
            "target": target_s,
            "state": state,
            "receipt": receipt.to_dict(),
            "current_diff": self.diff_receipt(receipt),
            "history_count": len(self.events.for_target(target_s)),
        }

    def history(self, target: ResourceRef | str) -> dict[str, Any]:
        target_s = str(ResourceRef.parse(target) if isinstance(target, str) else target)
        receipt_ids = [r.receipt_id for r in self.receipts.all() if r.target == target_s]
        events = list(self.events.for_target(target_s))
        return {"target": target_s, "receipt_ids": receipt_ids, "events": events}

    def graph(self, target: ResourceRef | str | None = None) -> dict[str, Any]:
        graph = DependencyGraph(self._active_receipts().values())
        target_s = None if target is None else str(ResourceRef.parse(target) if isinstance(target, str) else target)
        return graph.to_dict(target_s)

    def verify_integrity(self) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        try:
            receipts = self.receipts.all()
        except DependencyError as exc:
            return {"ok": False, "issues": [{"code": "receipt_store_invalid", "message": str(exc)}]}
        known_ids = {r.receipt_id for r in receipts}
        for receipt in receipts:
            for dep in receipt.dependencies:
                try:
                    self.comparators.validate_id(dep.comparator)
                    self.baselines.load(dep.snapshot_ref, expected_hash=dep.baseline_hash)
                except DependencyError as exc:
                    issues.append({"code": "dependency_evidence_invalid", "message": f"{receipt.receipt_id}: {exc}"})
        try:
            state = self.state.load()
            receipt_by_id = {r.receipt_id: r for r in receipts}
            for target, entry in state.get("targets", {}).items():
                rid = entry.get("last_receipt_id")
                if rid not in known_ids:
                    issues.append({"code": "state_receipt_missing", "message": f"{target}: {rid}"})
                    continue
                receipt = receipt_by_id[rid]
                if receipt.target != target:
                    issues.append({
                        "code": "state_receipt_target_mismatch",
                        "message": f"{target}: {rid} belongs to {receipt.target}",
                    })
                    continue
                allowed_changes = {dep.source for dep in receipt.dependencies}
                if receipt.builder_id is not None:
                    allowed_changes.add(f"builder://{receipt.builder_id}")
                if receipt.semantic_rule_id is not None:
                    allowed_changes.add(f"rule://{receipt.semantic_rule_id}")
                unknown_changes = sorted(set(entry.get("changed_dependencies", [])) - allowed_changes)
                if unknown_changes:
                    issues.append({
                        "code": "state_changed_dependency_unknown",
                        "message": f"{target}: {unknown_changes}",
                    })
                if entry.get("status") == "valid" and not receipt.audit_complete:
                    issues.append({
                        "code": "state_valid_with_incomplete_audit",
                        "message": f"{target}: {rid}",
                    })
            events = self.events.all()
            for event in events:
                rid = event.get("receipt_id")
                if rid not in known_ids:
                    issues.append({"code": "event_receipt_missing", "message": f"{event.get('event_id')}: {rid}"})
                    continue
                receipt = receipt_by_id[rid]
                if receipt.target != event.get("target"):
                    issues.append({
                        "code": "event_receipt_target_mismatch",
                        "message": f"{event.get('event_id')}: {event.get('target')} vs {receipt.target}",
                    })
                    continue
                allowed_changes = {dep.source for dep in receipt.dependencies}
                if receipt.builder_id is not None:
                    allowed_changes.add(f"builder://{receipt.builder_id}")
                if receipt.semantic_rule_id is not None:
                    allowed_changes.add(f"rule://{receipt.semantic_rule_id}")
                review = event.get("review")
                if isinstance(review, dict):
                    if receipt.semantic_rule_id is None:
                        issues.append({
                            "code": "semantic_review_receipt_missing_rule_identity",
                            "message": f"{event.get('event_id')}: review event points to receipt without semantic rule identity",
                        })
                    elif review.get("rule_id") != receipt.semantic_rule_id or review.get("rule_revision") != receipt.semantic_rule_revision:
                        issues.append({
                            "code": "semantic_review_rule_mismatch",
                            "message": f"{event.get('event_id')}: review rule identity does not match receipt",
                        })
                    prior_id = review.get("prior_receipt_id")
                    if prior_id is not None:
                        prior = receipt_by_id.get(prior_id)
                        if prior is None:
                            issues.append({
                                "code": "semantic_review_prior_receipt_missing",
                                "message": f"{event.get('event_id')}: {prior_id}",
                            })
                        elif prior.target != event.get("target"):
                            issues.append({
                                "code": "semantic_review_prior_receipt_target_mismatch",
                                "message": f"{event.get('event_id')}: prior receipt belongs to {prior.target}",
                            })
                        else:
                            allowed_changes.update(dep.source for dep in prior.dependencies)
                            if prior.semantic_rule_id is not None:
                                allowed_changes.add(f"rule://{prior.semantic_rule_id}")
                unknown_changes = sorted(set(event.get("changed_dependencies", [])) - allowed_changes)
                if unknown_changes:
                    issues.append({
                        "code": "event_changed_dependency_unknown",
                        "message": f"{event.get('event_id')}: {unknown_changes}",
                    })
            events_by_target: dict[str, list[dict[str, Any]]] = {}
            for event in events:
                events_by_target.setdefault(event["target"], []).append(event)
            for target, entry in state.get("targets", {}).items():
                target_events = [e for e in events_by_target.get(target, []) if e.get("state_revision") is not None]
                if target_events:
                    latest_target_event = max(target_events, key=lambda e: e["state_revision"])
                    if latest_target_event.get("receipt_id") != entry.get("last_receipt_id") or latest_target_event.get("status") != entry.get("status"):
                        issues.append({
                            "code": "state_latest_event_mismatch",
                            "message": f"{target}: state {entry.get('status')}/{entry.get('last_receipt_id')} vs latest event {latest_target_event.get('status')}/{latest_target_event.get('receipt_id')}",
                        })
                rid = entry.get("last_receipt_id")
                receipt = receipt_by_id.get(rid)
                if receipt is not None and receipt.semantic_rule_id is not None and entry.get("status") == "valid":
                    semantic_events = [
                        e for e in events_by_target.get(target, [])
                        if e.get("receipt_id") == rid
                        and e.get("event_type") == "semantic_validation"
                        and isinstance(e.get("review"), dict)
                    ]
                    if not semantic_events:
                        issues.append({
                            "code": "semantic_valid_without_review_event",
                            "message": f"{target}: semantic receipt {rid} is valid without an explicit semantic_validation event",
                        })
                    elif not any(
                        e["review"].get("rule_id") == receipt.semantic_rule_id
                        and e["review"].get("rule_revision") == receipt.semantic_rule_revision
                        for e in semantic_events
                    ):
                        issues.append({
                            "code": "semantic_review_rule_mismatch",
                            "message": f"{target}: semantic validation event does not match receipt rule identity",
                        })

            revised_events = [e for e in events if e.get("state_revision") is not None]
            revisions = [e["state_revision"] for e in revised_events]
            if len(revisions) != len(set(revisions)):
                issues.append({
                    "code": "event_state_revision_duplicate",
                    "message": "multiple dependency events claim the same state_revision",
                })
            if revisions and max(revisions) > state.get("state_revision", 0):
                issues.append({
                    "code": "event_state_revision_ahead",
                    "message": f"event revision {max(revisions)} exceeds state revision {state.get('state_revision', 0)}",
                })
            current_revision = state.get("state_revision", 0)
            if current_revision > 0 and revised_events:
                latest_event = max(revised_events, key=lambda e: e["state_revision"])
                if latest_event["state_revision"] != current_revision:
                    issues.append({
                        "code": "state_event_revision_gap",
                        "message": f"state revision {current_revision} has no matching latest dependency event",
                    })
        except DependencyError as exc:
            issues.append({"code": "runtime_state_invalid", "message": str(exc)})
        return {"ok": not issues, "issues": issues, "receipt_count": len(receipts)}


__all__ = [
    "BaselineError",
    "BaselineSnapshot",
    "BaselineStore",
    "ComparatorError",
    "ComparatorRegistry",
    "DependencyEntry",
    "DependencyError",
    "DependencyGraph",
    "DependencyReceipt",
    "DependencyRuntime",
    "DependencyStateEntry",
    "DiffResult",
    "EventStore",
    "ExplicitDependency",
    "ReceiptError",
    "ReceiptStore",
    "StateError",
    "StateStore",
]
