"""P7 file-runtime hardening: locks, write-ahead rollback journals and migrations.

The runtime remains file based.  P7 adds a single-writer/shared-reader process lock
outside the project tree plus a project-owned transaction journal that can roll back
an interrupted multi-file mutation on the next explicit recovery.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Iterator, Mapping
import uuid

from .project import ProjectRoots, is_within
from .versions import RUNTIME_LAYOUT_VERSION

try:  # POSIX path used by the acceptance environment.
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback below
    fcntl = None  # type: ignore

try:  # pragma: no cover - Windows only
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover
    msvcrt = None  # type: ignore


LEGACY_LAYOUT_VERSION = "legacy-p6-unmarked"


class HardeningError(RuntimeError):
    pass


class LockBusyError(HardeningError):
    pass


class RecoveryRequiredError(HardeningError):
    pass


class MigrationError(HardeningError):
    pass


class TransactionError(HardeningError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HardeningError(f"{label} must be a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HardeningError(f"{label} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise HardeningError(f"{label} must include timezone information")
    return value


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _canonical_rel_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise HardeningError(f"{label} must be a canonical relative POSIX path")
    posix = PurePosixPath(value)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts) or posix.as_posix() != value:
        raise HardeningError(f"{label} must be a canonical relative POSIX path: {value!r}")
    return value


def _valid_transaction_id(value: Any) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"txn-[0-9a-f-]{36}", value) is None:
        return False
    try:
        parsed = uuid.UUID(value[4:])
    except ValueError:
        return False
    return str(parsed) == value[4:]


def _real_stage_root(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise HardeningError(f"transaction stage must be a real directory: {path.name}")


def _journal_temp_name(name: str) -> bool:
    return re.fullmatch(r"journal\.json\.tmp-[0-9]+-[0-9a-f]{8}", name) is not None


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _direct_atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        _fsync_dir(path.parent)
    finally:
        tmp.unlink(missing_ok=True)


_ACTIVE_TRANSACTION: ContextVar["FileTransaction | None"] = ContextVar(
    "docengine_active_transaction", default=None
)


def active_transaction() -> "FileTransaction | None":
    return _ACTIVE_TRANSACTION.get()


def before_file_mutation(path: Path, *, planned_after_hash: str | None = None) -> None:
    tx = active_transaction()
    if tx is not None:
        tx.before_write(path, planned_after_hash=planned_after_hash)


def after_file_mutation(path: Path) -> None:
    tx = active_transaction()
    if tx is not None:
        tx.after_write(path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    before_file_mutation(path, planned_after_hash="sha256:" + _sha256(data))
    _direct_atomic_write(path, data)
    after_file_mutation(path)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def append_text(path: Path, text: str) -> None:
    prior = path.read_bytes() if path.exists() else b""
    atomic_write_bytes(path, prior + text.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class RuntimeLock:
    path: Path
    shared: bool
    handle: Any

    def close(self) -> None:
        try:
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.handle.close()


class LockManager:
    """External per-documentation-root lock; read locks do not mutate the project."""

    def __init__(self, roots: ProjectRoots) -> None:
        identity = str(roots.documentation_root.resolve(strict=False)).encode("utf-8")
        digest = hashlib.sha256(identity).hexdigest()
        lock_root = Path(tempfile.gettempdir()) / "docengine-runtime-locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        self.path = lock_root / f"{digest}.lock"

    def acquire(self, *, shared: bool) -> RuntimeLock:
        handle = self.path.open("a+b")
        try:
            if fcntl is not None:
                flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                try:
                    fcntl.flock(handle.fileno(), flags | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise LockBusyError(
                        f"documentation runtime is busy with another {'reader' if shared else 'writer'}: {self.path}"
                    ) from exc
            elif msvcrt is not None:  # pragma: no cover - Windows
                # Windows stdlib has no shared lock primitive; serialize safely.
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise LockBusyError(f"documentation runtime is busy: {self.path}") from exc
            else:  # pragma: no cover
                raise HardeningError("no supported OS file-lock primitive")
            return RuntimeLock(self.path, shared, handle)
        except Exception:
            handle.close()
            raise

    @contextmanager
    def held(self, *, shared: bool) -> Iterator[RuntimeLock]:
        lock = self.acquire(shared=shared)
        try:
            yield lock
        finally:
            lock.close()


class FileTransaction:
    """Immediate-write transaction with durable pre-images for crash rollback."""

    def __init__(self, roots: ProjectRoots, operation: str) -> None:
        self.roots = roots
        self.operation = operation
        self.documentation_root = roots.documentation_root.resolve(strict=False)
        dep = roots.documentation_root / roots.config.dependency_dir
        dep_resolved = dep.resolve(strict=False)
        if not is_within(dep_resolved, self.documentation_root):
            raise TransactionError("dependency runtime directory escapes documentation root")
        if dep.is_symlink():
            raise TransactionError("dependency runtime directory must not be a symlink")
        self.hardening_root = dep / "hardening"
        self.tx_root = self.hardening_root / "transactions"
        self.preparation_root = self.hardening_root / "transaction_preparation"
        self.cleanup_root = self.hardening_root / "transaction_cleanup"
        if any(p.is_symlink() for p in (self.hardening_root, self.tx_root, self.preparation_root, self.cleanup_root)):
            raise TransactionError("hardening transaction path must not contain symlinks")
        self.transaction_id = f"txn-{uuid.uuid4()}"
        self.path = self.tx_root / self.transaction_id
        self.journal_path = self.path / "journal.json"
        self._ops: dict[str, dict[str, Any]] = {}
        self._token = None
        self._write_count = 0

    def _activate(self) -> None:
        HardeningManager._validate_preparation(self.path)
        HardeningManager._parse_journal(self.path)  # a complete journal is mandatory
        destination = self.tx_root / self.transaction_id
        _real_stage_root(self.tx_root)
        self.tx_root.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise TransactionError(f"active transaction identity already exists: {self.transaction_id}")
        os.rename(self.path, destination)
        self.path = destination
        self.journal_path = self.path / "journal.json"
        _fsync_dir(self.tx_root)
        _fsync_dir(self.preparation_root)

    def _relative(self, path: Path) -> str:
        resolved = path.resolve(strict=False)
        if not is_within(resolved, self.documentation_root):
            raise TransactionError(f"transaction target escapes documentation root: {path}")
        # Serialize the path from the same canonical identities used for the
        # confinement check.  On Windows the same directory can be spelled
        # through an 8.3 alias (for example RUNNER~1) or its long name; mixing
        # canonical and lexical paths makes Path.relative_to() reject a target
        # that is physically inside the documentation root.
        return resolved.relative_to(self.documentation_root).as_posix()

    def _journal(self, phase: str) -> dict[str, Any]:
        return {
            "journal_schema_version": "1.0.0",
            "transaction_id": self.transaction_id,
            "operation": self.operation,
            "phase": phase,
            "started_at": self.started_at,
            "updated_at": _utc_now(),
            "operations": [self._ops[k] for k in sorted(self._ops)],
        }

    def _write_journal(self, phase: str) -> None:
        _direct_atomic_write(
            self.journal_path,
            json.dumps(self._journal(phase), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n",
        )

    def __enter__(self) -> "FileTransaction":
        if active_transaction() is not None:
            raise TransactionError("nested hardening transactions are not supported")
        self.started_at = _utc_now()
        _real_stage_root(self.preparation_root)
        self.path = self.preparation_root / self.transaction_id
        self.journal_path = self.path / "journal.json"
        self.path.mkdir(parents=True, exist_ok=False)
        _fsync_dir(self.path.parent)
        self._write_journal("open")
        _fsync_dir(self.path)
        self._activate()
        self._token = _ACTIVE_TRANSACTION.set(self)
        return self

    def before_write(self, path: Path, *, planned_after_hash: str | None = None) -> None:
        if self._token is None or active_transaction() is not self:
            raise TransactionError("target writes require an activated transaction")
        rel = self._relative(path)
        if rel in self._ops:
            op = self._ops[rel]
            if planned_after_hash is not None and planned_after_hash not in op.setdefault("planned_after_hashes", []):
                op["planned_after_hashes"].append(planned_after_hash)
                self._write_journal("open")
            return
        backup_name = None
        existed = path.exists()
        if path.is_symlink():
            raise TransactionError(f"transaction refuses symlink target: {path}")
        before_hash = None
        if existed:
            if not path.is_file():
                raise TransactionError(f"transaction target is not a file: {path}")
            data = path.read_bytes()
            before_hash = "sha256:" + _sha256(data)
            backup_name = f"backup-{len(self._ops):05d}.bin"
            backup = self.path / backup_name
            with backup.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        self._ops[rel] = {
            "path": rel,
            "existed": existed,
            "backup": backup_name,
            "before_hash": before_hash,
            "planned_after_hashes": [] if planned_after_hash is None else [planned_after_hash],
        }
        # Pre-image must be durable before target mutation.
        self._write_journal("open")
        _fsync_dir(self.path)

    def after_write(self, path: Path) -> None:
        rel = self._relative(path)
        op = self._ops.get(rel)
        if op is None:
            raise TransactionError(f"write completed without journal pre-image: {rel}")
        if path.exists() and path.is_file() and not path.is_symlink():
            actual_hash = "sha256:" + _sha256(path.read_bytes())
            op["after_hash"] = actual_hash
            if actual_hash not in op.setdefault("planned_after_hashes", []):
                op["planned_after_hashes"].append(actual_hash)
        self._write_count += 1
        self._write_journal("open")
        crash_after = os.environ.get("DOCENGINE_TEST_CRASH_AFTER_WRITES")
        if crash_after:
            try:
                threshold = int(crash_after)
            except ValueError:
                threshold = -1
            if threshold > 0 and self._write_count >= threshold:
                os._exit(91)  # test-only hard-crash injection; intentionally bypasses cleanup

    def commit(self) -> None:
        self._write_journal("committed")
        _fsync_dir(self.path)
        HardeningManager(self.roots)._retire_transaction(self.path, "committed")

    def rollback(self) -> None:
        # Restore in reverse registration order. Repeating rollback is idempotent.
        for rel, op in reversed(list(self._ops.items())):
            target = self.roots.documentation_root / rel
            if op["existed"]:
                backup = self.path / str(op["backup"])
                if not backup.is_file():
                    raise TransactionError(f"transaction backup missing for {rel}")
                _direct_atomic_write(target, backup.read_bytes())
            else:
                if target.exists():
                    if target.is_symlink() or not target.is_file():
                        raise TransactionError(f"cannot rollback non-file transaction target: {target}")
                    target.unlink()
                    _fsync_dir(target.parent)

    def __exit__(self, exc_type, exc, tb) -> bool:
        assert self._token is not None
        _ACTIVE_TRANSACTION.reset(self._token)
        if exc_type is None:
            self.commit()
            return False
        # Never destroy the only recovery journal/pre-images when synchronous
        # rollback itself fails.  A later explicit recovery must still be able to
        # diagnose the interrupted transaction.
        self.rollback()
        HardeningManager(self.roots)._retire_transaction(self.path, "rolled_back")
        return False


class HardeningManager:
    def __init__(self, roots: ProjectRoots) -> None:
        self.roots = roots
        self.lock_manager = LockManager(roots)
        self.docs = roots.documentation_root.resolve(strict=False)
        self.dep = roots.documentation_root / roots.config.dependency_dir
        dep_resolved = self.dep.resolve(strict=False)
        if not is_within(dep_resolved, self.docs):
            raise HardeningError("dependency runtime directory escapes documentation root")
        if self.dep.is_symlink():
            raise HardeningError("dependency runtime directory must not be a symlink")
        self.hardening_root = self.dep / "hardening"
        self.tx_root = self.hardening_root / "transactions"
        self.preparation_root = self.hardening_root / "transaction_preparation"
        self.cleanup_root = self.hardening_root / "transaction_cleanup"
        if any(p.is_symlink() for p in (self.hardening_root, self.tx_root, self.preparation_root, self.cleanup_root)):
            raise HardeningError("hardening runtime path must not contain symlinks")
        self.recovery_events = self.hardening_root / "recovery_events.jsonl"

    @classmethod
    def _validate_preparation(cls, directory: Path) -> None:
        if directory.is_symlink() or not directory.is_dir() or not _valid_transaction_id(directory.name):
            raise HardeningError(f"invalid transaction preparation: {directory.name}")
        for entry in directory.iterdir():
            if entry.is_symlink() or not entry.is_file() or (entry.name != "journal.json" and not _journal_temp_name(entry.name)):
                raise HardeningError(f"unknown preparation contents: {directory.name}/{entry.name}")
        if (directory / "journal.json").exists():
            journal = cls._parse_journal(directory)
            if journal["phase"] != "open" or journal["operations"]:
                raise HardeningError(f"preparation contains active transaction evidence: {directory.name}")

    @staticmethod
    def _parse_cleanup_ticket(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file() or not _valid_transaction_id(path.stem) or path.suffix != ".json":
            raise HardeningError(f"invalid cleanup ticket: {path.name}")
        try:
            ticket = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HardeningError(f"invalid cleanup ticket JSON: {path.name}: {exc}") from exc
        required = {"cleanup_schema_version", "transaction_id", "outcome", "journal_hash", "completed_at"}
        if not isinstance(ticket, dict) or set(ticket) != required or ticket.get("cleanup_schema_version") != "1.0.0":
            raise HardeningError(f"invalid cleanup ticket shape/version: {path.name}")
        if ticket["transaction_id"] != path.stem or not isinstance(ticket["outcome"], str) or ticket["outcome"] not in {"committed", "rolled_back"} or not _is_sha256(ticket["journal_hash"]):
            raise HardeningError(f"invalid cleanup ticket authority: {path.name}")
        _parse_timestamp(ticket["completed_at"], label=f"cleanup {path.stem} completed_at")
        return ticket

    @classmethod
    def _validate_cleanup_payload(cls, directory: Path, ticket: Mapping[str, Any], *, active: bool = False) -> None:
        if directory.is_symlink() or not directory.is_dir() or directory.name != ticket["transaction_id"]:
            raise HardeningError(f"invalid cleanup payload: {directory.name}")
        journal = directory / "journal.json"
        if journal.exists() or journal.is_symlink() or active:
            parsed = cls._parse_journal(directory)
            if "sha256:" + _sha256(journal.read_bytes()) != ticket["journal_hash"]:
                raise HardeningError(f"cleanup journal hash mismatch: {directory.name}")
            expected = "committed" if ticket["outcome"] == "committed" else "open"
            if parsed["phase"] != expected:
                raise HardeningError(f"cleanup outcome/journal mismatch: {directory.name}")
        for entry in directory.iterdir():
            allowed = entry.name == "journal.json" or _journal_temp_name(entry.name) or re.fullmatch(r"backup-[0-9]{5}\.bin", entry.name)
            if not allowed or entry.is_symlink() or not entry.is_file():
                raise HardeningError(f"unknown cleanup payload contents: {directory.name}/{entry.name}")

    def _publish_cleanup_ticket(self, directory: Path, outcome: str) -> dict[str, Any]:
        _real_stage_root(self.cleanup_root)
        self.cleanup_root.mkdir(parents=True, exist_ok=True)
        ticket_path = self.cleanup_root / (directory.name + ".json")
        ticket = {"cleanup_schema_version": "1.0.0", "transaction_id": directory.name,
                  "outcome": outcome, "journal_hash": "sha256:" + _sha256((directory / "journal.json").read_bytes()),
                  "completed_at": _utc_now()}
        self._validate_cleanup_payload(directory, ticket, active=True)
        if ticket_path.exists() or ticket_path.is_symlink():
            existing = self._parse_cleanup_ticket(ticket_path)
            if any(existing[k] != ticket[k] for k in ("transaction_id", "outcome", "journal_hash")):
                raise HardeningError(f"conflicting cleanup ticket: {directory.name}")
            return existing
        _direct_atomic_write(ticket_path, _canonical_json(ticket) + b"\n")
        return ticket

    def _move_to_cleanup(self, directory: Path) -> Path:
        destination = self.cleanup_root / directory.name
        if destination.exists() or destination.is_symlink():
            raise HardeningError(f"active and cleanup transaction both exist: {directory.name}")
        os.rename(directory, destination)
        _fsync_dir(self.cleanup_root)
        _fsync_dir(self.tx_root)
        return destination

    def _finish_cleanup(self, ticket: Mapping[str, Any]) -> None:
        directory = self.cleanup_root / str(ticket["transaction_id"])
        if directory.exists() or directory.is_symlink():
            self._validate_cleanup_payload(directory, ticket)
            shutil.rmtree(directory)
            _fsync_dir(self.cleanup_root)
        # The authority stays outside the recursively deleted payload until last.
        (self.cleanup_root / (str(ticket["transaction_id"]) + ".json")).unlink()
        _fsync_dir(self.cleanup_root)

    def _retire_transaction(self, directory: Path, outcome: str) -> None:
        if outcome not in {"committed", "rolled_back"}:
            raise HardeningError(f"invalid transaction completion outcome: {outcome}")
        journal = self._parse_journal(directory)
        if directory.parent != self.tx_root or journal["phase"] != ("committed" if outcome == "committed" else "open"):
            raise HardeningError(f"invalid transaction retirement: {directory.name}")
        ticket = self._publish_cleanup_ticket(directory, outcome)
        self._validate_cleanup_payload(directory, ticket, active=True)
        self._move_to_cleanup(directory)
        self._finish_cleanup(ticket)

    @staticmethod
    def _validate_operation(op: Any, *, txid: str, index: int) -> dict[str, Any]:
        if not isinstance(op, dict):
            raise HardeningError(f"transaction {txid} operation {index} must be an object")
        required = {"path", "existed", "backup", "before_hash", "planned_after_hashes"}
        allowed = required | {"after_hash"}
        if not required.issubset(op) or not set(op).issubset(allowed):
            raise HardeningError(f"transaction {txid} operation {index} has invalid keys")
        path = _canonical_rel_path(op.get("path"), label=f"transaction {txid} operation path")
        existed = op.get("existed")
        if not isinstance(existed, bool):
            raise HardeningError(f"transaction {txid} operation {path} existed must be boolean")
        backup = op.get("backup")
        before_hash = op.get("before_hash")
        if existed:
            if not isinstance(backup, str) or re.fullmatch(r"backup-[0-9]{5}\.bin", backup) is None:
                raise HardeningError(f"transaction {txid} operation {path} requires canonical backup name")
            if not _is_sha256(before_hash):
                raise HardeningError(f"transaction {txid} operation {path} requires before_hash")
        else:
            if backup is not None or before_hash is not None:
                raise HardeningError(f"transaction {txid} new-file operation {path} must not carry backup/before_hash")
        planned = op.get("planned_after_hashes")
        if not isinstance(planned, list) or not all(_is_sha256(x) for x in planned) or len(planned) != len(set(planned)):
            raise HardeningError(f"transaction {txid} operation {path} has invalid planned_after_hashes")
        after_hash = op.get("after_hash")
        if after_hash is not None:
            if not _is_sha256(after_hash):
                raise HardeningError(f"transaction {txid} operation {path} has invalid after_hash")
            if after_hash not in planned:
                raise HardeningError(f"transaction {txid} operation {path} after_hash is not a planned hash")
        return dict(op)

    @classmethod
    def _parse_journal(cls, directory: Path) -> dict[str, Any]:
        if directory.is_symlink() or not directory.is_dir():
            raise HardeningError(f"transaction entry is not a real directory: {directory.name}")
        if not _valid_transaction_id(directory.name):
            raise HardeningError(f"invalid transaction directory name: {directory.name!r}")
        journal = directory / "journal.json"
        if not journal.is_file() or journal.is_symlink():
            raise HardeningError(f"transaction journal missing or symlinked: {directory.name}")
        try:
            payload = json.loads(journal.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HardeningError(f"invalid transaction journal JSON for {directory.name}: {exc}") from exc
        if not isinstance(payload, dict):
            raise HardeningError(f"transaction journal must be an object: {directory.name}")
        required = {"journal_schema_version", "transaction_id", "operation", "phase", "started_at", "updated_at", "operations"}
        if set(payload) != required:
            raise HardeningError(f"transaction journal has invalid keys: {directory.name}")
        if payload.get("journal_schema_version") != "1.0.0":
            raise HardeningError(f"unsupported transaction journal schema: {directory.name}")
        txid = payload.get("transaction_id")
        if not _valid_transaction_id(txid) or txid != directory.name:
            raise HardeningError(f"transaction id/directory mismatch: {directory.name}")
        if not isinstance(payload.get("operation"), str) or not payload["operation"]:
            raise HardeningError(f"transaction operation must be non-empty: {txid}")
        if not isinstance(payload.get("phase"), str) or payload["phase"] not in {"open", "committed"}:
            raise HardeningError(f"invalid transaction phase for {txid}: {payload.get('phase')!r}")
        _parse_timestamp(payload.get("started_at"), label=f"transaction {txid} started_at")
        _parse_timestamp(payload.get("updated_at"), label=f"transaction {txid} updated_at")
        operations = payload.get("operations")
        if not isinstance(operations, list):
            raise HardeningError(f"transaction operations must be an array: {txid}")
        validated: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for index, op in enumerate(operations):
            parsed = cls._validate_operation(op, txid=txid, index=index)
            if parsed["path"] in seen_paths:
                raise HardeningError(f"duplicate transaction operation path in {txid}: {parsed['path']}")
            seen_paths.add(parsed["path"])
            validated.append(parsed)
        result = dict(payload)
        result["operations"] = validated
        return result

    def pending_transactions(self) -> list[dict[str, Any]]:
        for root in (self.tx_root, self.preparation_root, self.cleanup_root):
            _real_stage_root(root)
        pending: list[dict[str, Any]] = []
        linked_active: set[str] = set()
        cleanup_entries = list(self.cleanup_root.iterdir()) if self.cleanup_root.exists() else []
        ticket_names = {entry.stem for entry in cleanup_entries if entry.suffix == ".json"}
        for entry in sorted(cleanup_entries, key=lambda p: p.name):
            try:
                if entry.suffix == ".json":
                    ticket = self._parse_cleanup_ticket(entry)
                    active = self.tx_root / ticket["transaction_id"]
                    payload = self.cleanup_root / ticket["transaction_id"]
                    has_active = active.exists() or active.is_symlink()
                    has_payload = payload.exists() or payload.is_symlink()
                    if has_active and has_payload:
                        raise HardeningError(f"active and cleanup transaction both exist: {entry.stem}")
                    if has_active:
                        self._validate_cleanup_payload(active, ticket, active=True)
                        linked_active.add(entry.stem)
                    elif has_payload:
                        self._validate_cleanup_payload(payload, ticket)
                    pending.append({**ticket, "phase": "cleanup", "cleanup_only": True,
                                    "lifecycle_stage": "active_cleanup" if has_active else "cleanup"})
                elif _valid_transaction_id(entry.name) and entry.name in ticket_names:
                    # This payload is inspected through its external ticket.
                    continue
                elif re.fullmatch(r"txn-[0-9a-f-]{36}\.json\.tmp-[0-9]+-[0-9a-f]{8}", entry.name) and _valid_transaction_id(entry.name[:40]):
                    if entry.is_symlink() or not entry.is_file():
                        raise HardeningError(f"invalid cleanup temporary file: {entry.name}")
                    pending.append({"transaction_id": entry.name[:40], "phase": "cleanup", "cleanup_only": True,
                                    "lifecycle_stage": "cleanup_temporary", "temporary_name": entry.name})
                else:
                    raise HardeningError(f"unknown cleanup entry or missing ticket: {entry.name}")
            except HardeningError as exc:
                pending.append({"transaction_id": entry.name, "phase": "corrupt", "error": str(exc)})
        if self.preparation_root.exists():
            for entry in sorted(self.preparation_root.iterdir(), key=lambda p: p.name):
                try:
                    self._validate_preparation(entry)
                    if (self.tx_root / entry.name).exists() or (self.cleanup_root / entry.name).exists() or entry.name in ticket_names:
                        raise HardeningError(f"transaction preparation identity conflict: {entry.name}")
                    pending.append({"transaction_id": entry.name, "phase": "preparing", "cleanup_only": True,
                                    "lifecycle_stage": "preparation"})
                except HardeningError as exc:
                    pending.append({"transaction_id": entry.name, "phase": "corrupt", "error": str(exc)})
        active_entries = list(self.tx_root.iterdir()) if self.tx_root.exists() else []
        for entry in sorted(active_entries, key=lambda p: p.name):
            if entry.name in linked_active:
                continue
            try:
                payload = self._parse_journal(entry)
            except HardeningError as exc:
                pending.append({"transaction_id": entry.name, "phase": "corrupt", "error": str(exc)})
                continue
            if payload["phase"] == "committed":
                pending.append({**payload, "cleanup_only": True})
            else:
                pending.append(payload)
        return pending

    @staticmethod
    def _validate_recovery_event(event: Any, *, lineno: int) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise HardeningError(f"recovery event line {lineno} must be an object")
        required = {"event_schema_version", "event_id", "recovered_at", "transaction_id", "operation", "action", "forced", "conflict_paths", "restored_paths"}
        if set(event) != required:
            raise HardeningError(f"recovery event line {lineno} has invalid keys")
        if event.get("event_schema_version") != "1.0.0":
            raise HardeningError(f"unsupported recovery event schema at line {lineno}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.startswith("recovery-"):
            raise HardeningError(f"invalid recovery event_id at line {lineno}")
        try:
            if str(uuid.UUID(event_id[len("recovery-"):])) != event_id[len("recovery-"):]:
                raise ValueError
        except ValueError as exc:
            raise HardeningError(f"invalid recovery event_id at line {lineno}") from exc
        _parse_timestamp(event.get("recovered_at"), label=f"recovery event line {lineno} recovered_at")
        if not _valid_transaction_id(event.get("transaction_id")):
            raise HardeningError(f"invalid recovery transaction_id at line {lineno}")
        if event.get("operation") is not None and (not isinstance(event.get("operation"), str) or not event["operation"]):
            raise HardeningError(f"invalid recovery operation at line {lineno}")
        if event.get("action") != "rolled_back_interrupted_transaction":
            raise HardeningError(f"invalid recovery action at line {lineno}")
        if not isinstance(event.get("forced"), bool):
            raise HardeningError(f"recovery forced must be boolean at line {lineno}")
        for key in ("conflict_paths", "restored_paths"):
            values = event.get(key)
            if not isinstance(values, list) or not all(isinstance(x, str) for x in values) or len(values) != len(set(values)):
                raise HardeningError(f"recovery {key} must be unique strings at line {lineno}")
            for value in values:
                _canonical_rel_path(value, label=f"recovery {key} line {lineno}")
        if not set(event["conflict_paths"]).issubset(set(event["restored_paths"])):
            raise HardeningError(f"recovery conflict_paths must be a subset of restored_paths at line {lineno}")
        return dict(event)

    def recovery_history(self) -> tuple[dict[str, Any], ...]:
        if not self.recovery_events.exists():
            return ()
        if self.recovery_events.is_symlink() or not self.recovery_events.is_file():
            raise HardeningError("recovery event log must be a regular file")
        events: list[dict[str, Any]] = []
        ids: set[str] = set()
        try:
            lines = self.recovery_events.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise HardeningError(f"recovery event log is not UTF-8: {exc}") from exc
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HardeningError(f"invalid recovery event JSON at line {lineno}: {exc}") from exc
            event = self._validate_recovery_event(raw, lineno=lineno)
            if event["event_id"] in ids:
                raise HardeningError(f"duplicate recovery event_id at line {lineno}: {event['event_id']}")
            ids.add(event["event_id"])
            events.append(event)
        return tuple(events)

    def _append_recovery_event(self, event: Mapping[str, Any]) -> None:
        self.recovery_history()  # never extend a corrupt audit log
        existing = self.recovery_events.read_bytes() if self.recovery_events.exists() else b""
        line = _canonical_json(dict(event)) + b"\n"
        _direct_atomic_write(self.recovery_events, existing + line)

    def _preflight_recovery(self, journal: Mapping[str, Any], directory: Path, *, force: bool) -> tuple[list[tuple[dict[str, Any], Path, bytes | None]], list[str]]:
        txid = str(journal["transaction_id"])
        prepared: list[tuple[dict[str, Any], Path, bytes | None]] = []
        conflict_paths: list[str] = []
        for op in reversed(list(journal["operations"])):
            target = self.roots.documentation_root / op["path"]
            resolved = target.resolve(strict=False)
            if not is_within(resolved, self.docs):
                raise RecoveryRequiredError(f"transaction target escapes docs during recovery: {op['path']}")
            if target.exists() and (target.is_symlink() or not target.is_file()):
                raise RecoveryRequiredError(f"cannot recover non-file transaction target: {op['path']}")
            current_hash = "sha256:" + _sha256(target.read_bytes()) if target.exists() else None
            known_after = set(op["planned_after_hashes"])
            before_hash = op["before_hash"]
            allowed_current = set(known_after)
            if before_hash is not None:
                allowed_current.add(before_hash)

            conflict = False
            if op["existed"]:
                # A missing pre-existing file cannot be produced by our atomic write;
                # it is therefore an external post-crash change unless force is used.
                conflict = current_hash is None or current_hash not in allowed_current
            elif current_hash is not None:
                # A transaction-created path may be absent (already rolled back), or
                # contain one of the known transaction outputs. Anything else is external.
                conflict = not allowed_current or current_hash not in allowed_current
            if conflict:
                if not force:
                    raise RecoveryRequiredError(
                        f"transaction target changed outside interrupted operation; refusing overwrite: {op['path']}"
                    )
                conflict_paths.append(op["path"])

            backup_data: bytes | None = None
            if op["existed"]:
                backup = directory / str(op["backup"])
                if backup.parent != directory or not backup.is_file() or backup.is_symlink():
                    raise RecoveryRequiredError(f"missing or unsafe transaction backup for {op['path']} in {txid}")
                backup_data = backup.read_bytes()
                if op["before_hash"] != "sha256:" + _sha256(backup_data):
                    raise RecoveryRequiredError(f"transaction backup checksum mismatch for {op['path']} in {txid}")
            prepared.append((op, target, backup_data))
        return prepared, sorted(set(conflict_paths))

    def recover(self, *, force: bool = False) -> dict[str, Any]:
        self.recovery_history()  # corruption in audit history is itself blocking evidence
        pending = self.pending_transactions()
        recovered: list[dict[str, Any]] = []
        for journal in pending:
            if journal.get("phase") == "corrupt":
                raise RecoveryRequiredError(f"cannot automatically recover corrupt transaction journal: {journal['transaction_id']}: {journal.get('error')}")
        for journal in pending:
            txid = str(journal.get("transaction_id", "unknown"))
            stage = journal.get("lifecycle_stage")
            if stage == "preparation":
                directory = self.preparation_root / txid
                self._validate_preparation(directory)
                shutil.rmtree(directory)
                _fsync_dir(self.preparation_root)
                recovered.append({"transaction_id": txid, "action": "discard_preparation"})
                continue
            if stage == "cleanup_temporary":
                (self.cleanup_root / journal["temporary_name"]).unlink(missing_ok=True)
                _fsync_dir(self.cleanup_root)
                recovered.append({"transaction_id": txid, "action": "discard_cleanup_temporary"})
                continue
            if stage in {"cleanup", "active_cleanup"}:
                if stage == "active_cleanup":
                    self._retire_transaction(self.tx_root / txid, journal["outcome"])
                else:
                    self._finish_cleanup(journal)
                recovered.append({"transaction_id": txid, "action": "cleanup_" + journal["outcome"]})
                continue
            directory = self.tx_root / txid
            if directory.parent != self.tx_root or not directory.is_dir() or directory.is_symlink():
                raise RecoveryRequiredError(f"unsafe transaction directory during recovery: {txid}")
            if journal["phase"] == "committed":
                self._retire_transaction(directory, "committed")
                recovered.append({"transaction_id": txid, "action": "cleanup_committed"})
                continue

            prepared, conflict_paths = self._preflight_recovery(journal, directory, force=force)
            # Only mutate after every operation/backup/conflict has passed preflight.
            for op, target, backup_data in prepared:
                if op["existed"]:
                    assert backup_data is not None
                    expected = op["before_hash"]
                    current_hash = "sha256:" + _sha256(target.read_bytes()) if target.exists() else None
                    if current_hash != expected:
                        _direct_atomic_write(target, backup_data)
                elif target.exists():
                    target.unlink()
                    _fsync_dir(target.parent)
            event = {
                "event_schema_version": "1.0.0",
                "event_id": f"recovery-{uuid.uuid4()}",
                "recovered_at": _utc_now(),
                "transaction_id": txid,
                "operation": journal.get("operation"),
                "action": "rolled_back_interrupted_transaction",
                "forced": bool(force),
                "conflict_paths": conflict_paths,
                "restored_paths": sorted(str(op["path"]) for op in journal["operations"]),
            }
            self._validate_recovery_event(event, lineno=0)
            self._append_recovery_event(event)
            self._retire_transaction(directory, "rolled_back")
            recovered.append(event)
        if self.tx_root.exists():
            _fsync_dir(self.tx_root)
        return {"pending_before": len(pending), "recovered": recovered, "remaining": len(self.pending_transactions())}

    @contextmanager
    def read_guard(self, *, allow_pending: bool = False) -> Iterator[None]:
        with self.lock_manager.held(shared=True):
            pending = [item for item in self.pending_transactions() if not item.get("cleanup_only")]
            if pending and not allow_pending:
                raise RecoveryRequiredError(
                    f"interrupted transaction requires recovery before read: {pending[0].get('transaction_id')}"
                )
            yield

    @contextmanager
    def write_guard(self, operation: str, *, transactional: bool = True) -> Iterator[dict[str, Any]]:
        with self.lock_manager.held(shared=False):
            recovery = self.recover()
            if transactional:
                with FileTransaction(self.roots, operation):
                    yield recovery
            else:
                yield recovery


@dataclass(frozen=True, slots=True)
class MigrationSpec:
    from_version: str
    to_version: str
    migration_id: str
    preserves_released_evidence: bool = True


class MigrationRegistry:
    def __init__(self) -> None:
        self._specs: dict[tuple[str, str], MigrationSpec] = {}

    def register(self, spec: MigrationSpec) -> None:
        key = (spec.from_version, spec.to_version)
        if key in self._specs:
            raise MigrationError(f"duplicate migration registration: {key}")
        self._specs[key] = spec

    def get(self, from_version: str, to_version: str) -> MigrationSpec:
        try:
            return self._specs[(from_version, to_version)]
        except KeyError as exc:
            raise MigrationError(f"no migration registered from {from_version!r} to {to_version!r}") from exc

    @property
    def specs(self) -> tuple[MigrationSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))


def default_migration_registry() -> MigrationRegistry:
    registry = MigrationRegistry()
    registry.register(MigrationSpec(
        from_version=LEGACY_LAYOUT_VERSION,
        to_version=RUNTIME_LAYOUT_VERSION,
        migration_id="p6-unmarked-to-runtime-layout-1",
        preserves_released_evidence=True,
    ))
    return registry


class MigrationManager:
    """Runtime-layout migration registry. P7 migrates P6 unmarked layout in-place.

    Existing receipts/baselines/state/events remain byte-identical because their
    released schema is already 1.0.0.  P7 introduces an explicit layout marker so
    future migrations cannot silently reset audit evidence.
    """

    def __init__(self, roots: ProjectRoots, registry: MigrationRegistry | None = None) -> None:
        self.roots = roots
        self.registry = registry or default_migration_registry()
        self.dep = roots.documentation_root / roots.config.dependency_dir
        self.hardening = self.dep / "hardening"
        if self.dep.is_symlink() or self.hardening.is_symlink():
            raise MigrationError("migration runtime path must not contain symlinks")
        self.marker = self.hardening / "runtime_layout.json"
        self.events = self.hardening / "migration_events.jsonl"

    def _has_runtime_evidence(self) -> bool:
        if not self.dep.exists():
            return False
        for rel in ("receipts", "baselines", "state/dependency_state.json", "state/materialization_state.json", "events/dependency_events.jsonl"):
            p = self.dep / rel
            if p.is_file():
                return True
            if p.is_dir() and any(p.iterdir()):
                return True
        return False

    @staticmethod
    def _validate_migration_event(event: Any, *, lineno: int, registry: MigrationRegistry) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise MigrationError(f"migration event line {lineno} must be an object")
        common = {"event_schema_version", "event_id", "recorded_at", "from_version", "to_version", "preserved_file_count"}
        init_allowed = common | {"action"}
        migrated_allowed = common | {"migration_id", "preserved_evidence_digest"}
        if event.get("from_version") is None:
            if set(event) != init_allowed:
                raise MigrationError(f"initialized migration event line {lineno} has invalid keys")
        else:
            if set(event) != migrated_allowed:
                raise MigrationError(f"migration event line {lineno} has invalid keys")
        if event.get("event_schema_version") != "1.0.0":
            raise MigrationError(f"unsupported migration event schema at line {lineno}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.startswith("migration-"):
            raise MigrationError(f"invalid migration event_id at line {lineno}")
        try:
            if str(uuid.UUID(event_id[len("migration-"):])) != event_id[len("migration-"):]:
                raise ValueError
        except ValueError as exc:
            raise MigrationError(f"invalid migration event_id at line {lineno}") from exc
        try:
            _parse_timestamp(event.get("recorded_at"), label=f"migration event line {lineno} recorded_at")
        except HardeningError as exc:
            raise MigrationError(str(exc)) from exc
        if event.get("to_version") != RUNTIME_LAYOUT_VERSION:
            raise MigrationError(f"unsupported migration event to_version at line {lineno}")
        count = event.get("preserved_file_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise MigrationError(f"invalid preserved_file_count at migration event line {lineno}")
        if event.get("from_version") is None:
            if event.get("action") != "initialized_runtime_layout" or count != 0:
                raise MigrationError(f"invalid initialized-runtime event at line {lineno}")
        else:
            from_version = event.get("from_version")
            migration_id = event.get("migration_id")
            digest = event.get("preserved_evidence_digest")
            if not isinstance(from_version, str) or not from_version:
                raise MigrationError(f"invalid from_version at migration event line {lineno}")
            if not isinstance(migration_id, str) or not migration_id:
                raise MigrationError(f"invalid migration_id at line {lineno}")
            if not _is_sha256(digest):
                raise MigrationError(f"invalid preserved_evidence_digest at migration event line {lineno}")
            spec = registry.get(from_version, RUNTIME_LAYOUT_VERSION)
            if spec.migration_id != migration_id:
                raise MigrationError(f"migration event line {lineno} does not match registered migration")
        return dict(event)

    def migration_history(self) -> tuple[dict[str, Any], ...]:
        if not self.events.exists():
            return ()
        if self.events.is_symlink() or not self.events.is_file():
            raise MigrationError("migration event log must be a regular file")
        try:
            lines = self.events.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise MigrationError(f"migration event log is not UTF-8: {exc}") from exc
        events: list[dict[str, Any]] = []
        ids: set[str] = set()
        for lineno, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MigrationError(f"invalid migration event JSON at line {lineno}: {exc}") from exc
            event = self._validate_migration_event(raw, lineno=lineno, registry=self.registry)
            if event["event_id"] in ids:
                raise MigrationError(f"duplicate migration event_id at line {lineno}: {event['event_id']}")
            ids.add(event["event_id"])
            events.append(event)
        return tuple(events)

    def inspect(self) -> dict[str, Any]:
        if not self.marker.exists():
            if self._has_runtime_evidence():
                return {"current": False, "version": LEGACY_LAYOUT_VERSION, "target_version": RUNTIME_LAYOUT_VERSION, "migration_required": True}
            return {"current": True, "version": RUNTIME_LAYOUT_VERSION, "target_version": RUNTIME_LAYOUT_VERSION, "migration_required": False, "implicit_empty": True}
        if self.marker.is_symlink() or not self.marker.is_file():
            raise MigrationError("runtime layout marker must be a regular file")
        try:
            data = json.loads(self.marker.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MigrationError(f"invalid runtime layout marker: {exc}") from exc
        if not isinstance(data, dict):
            raise MigrationError("runtime layout marker must be an object")
        allowed = {
            "runtime_layout_version", "initialized_at", "initialized_from_empty",
            "migrated_from", "migration_id", "migrated_at",
            "preserved_evidence_digest", "preserved_file_count",
        }
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise MigrationError(f"runtime layout marker has unknown keys: {unknown}")
        version = data.get("runtime_layout_version")
        if not isinstance(version, str):
            raise MigrationError("runtime layout marker missing version")
        if version != RUNTIME_LAYOUT_VERSION:
            raise MigrationError(f"unsupported runtime layout version {version!r}; expected {RUNTIME_LAYOUT_VERSION!r}")
        initialized = data.get("initialized_from_empty")
        migrated_from = data.get("migrated_from")
        if initialized is True:
            if set(data) != {"runtime_layout_version", "initialized_at", "initialized_from_empty"}:
                raise MigrationError("initialized runtime layout marker has invalid/mixed provenance fields")
            try:
                _parse_timestamp(data.get("initialized_at"), label="runtime layout initialized_at")
            except HardeningError as exc:
                raise MigrationError(str(exc)) from exc
        elif migrated_from is not None:
            required = {"runtime_layout_version", "migrated_from", "migration_id", "migrated_at", "preserved_evidence_digest", "preserved_file_count"}
            if set(data) != required:
                raise MigrationError("migrated runtime layout marker has invalid/mixed provenance fields")
            for key in ("migrated_from", "migration_id", "migrated_at", "preserved_evidence_digest"):
                if not isinstance(data.get(key), str) or not data[key]:
                    raise MigrationError(f"migrated runtime layout marker requires non-empty {key}")
            count = data.get("preserved_file_count")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise MigrationError("migrated runtime layout marker requires non-negative preserved_file_count")
            if not _is_sha256(data["preserved_evidence_digest"]):
                raise MigrationError("invalid preserved_evidence_digest in runtime layout marker")
            try:
                _parse_timestamp(data.get("migrated_at"), label="runtime layout migrated_at")
            except HardeningError as exc:
                raise MigrationError(str(exc)) from exc
            spec = self.registry.get(str(migrated_from), version)
            if spec.migration_id != data["migration_id"]:
                raise MigrationError("runtime layout migration provenance does not match registered migration")
        else:
            raise MigrationError("runtime layout marker must describe initialization or migration provenance")

        events = self.migration_history()
        if initialized is True:
            matched = any(
                event.get("from_version") is None
                and event.get("to_version") == version
                and event.get("action") == "initialized_runtime_layout"
                for event in events
            )
        else:
            matched = any(
                event.get("from_version") == data.get("migrated_from")
                and event.get("to_version") == version
                and event.get("migration_id") == data.get("migration_id")
                and event.get("preserved_evidence_digest") == data.get("preserved_evidence_digest")
                and event.get("preserved_file_count") == data.get("preserved_file_count")
                for event in events
            )
        if not matched:
            raise MigrationError("runtime layout marker has no matching migration audit event")
        return {"current": True, "version": version, "target_version": RUNTIME_LAYOUT_VERSION, "migration_required": False, "marker": data, "event_count": len(events)}

    def _evidence_files(self) -> list[Path]:
        files: list[Path] = []
        if not self.dep.exists():
            return files
        allowed_exact = {
            "state/dependency_state.json",
            "state/materialization_state.json",
            "events/dependency_events.jsonl",
        }
        for rel_root in ("receipts", "baselines", "state", "events"):
            root = self.dep / rel_root
            if not root.exists():
                continue
            if root.is_symlink() or not root.is_dir():
                raise MigrationError(f"legacy evidence root must be a real directory: {rel_root}")
            for entry in sorted(root.rglob("*")):
                rel = entry.relative_to(self.dep).as_posix()
                if entry.is_symlink():
                    raise MigrationError(f"legacy evidence must not contain symlinks: {rel}")
                if entry.is_dir():
                    continue
                if not entry.is_file():
                    raise MigrationError(f"legacy evidence contains non-file entry: {rel}")
                recognized = (
                    rel in allowed_exact
                    or (rel.startswith("receipts/") and re.fullmatch(r"receipts/receipt-[0-9a-f]{64}\.json", rel) is not None)
                    or (rel.startswith("baselines/") and re.fullmatch(r"baselines/sha256-[0-9a-f]{64}\.json", rel) is not None)
                )
                if not recognized:
                    raise MigrationError(f"unrecognized legacy evidence file: {rel}")
                files.append(entry)
        return sorted(files)

    def _validate_legacy_evidence(self) -> tuple[list[dict[str, Any]], str]:
        files = self._evidence_files()
        # Reuse the released P6 parsers/integrity checks instead of merely checking
        # that JSON can be decoded. Migration must not bless already-corrupt audit
        # evidence or silently omit symlinked entries from the preservation set.
        try:
            from .dependencies import DependencyError, DependencyRuntime
            from .materialization import MaterializationError, MaterializationStateStore

            runtime = DependencyRuntime(self.roots)
            integrity = runtime.verify_integrity()
            if not integrity.get("ok"):
                raise MigrationError(f"legacy dependency evidence is corrupt: {integrity.get('issues', [])}")
            for path in files:
                rel = path.relative_to(self.dep).as_posix()
                if rel.startswith("baselines/"):
                    digest = path.name[len("sha256-"):-len(".json")]
                    runtime.baselines.load(f"baseline://sha256/{digest}", expected_hash=f"sha256:{digest}")
            materialization = self.dep / "state" / "materialization_state.json"
            if materialization.exists():
                MaterializationStateStore(self.roots).load()
        except MigrationError:
            raise
        except (DependencyError, MaterializationError, OSError, ValueError) as exc:
            raise MigrationError(f"cannot migrate corrupt legacy evidence: {exc}") from exc

        records: list[dict[str, Any]] = []
        hasher = hashlib.sha256()
        for path in files:
            data = path.read_bytes()
            rel = path.relative_to(self.dep).as_posix()
            digest = "sha256:" + _sha256(data)
            records.append({"path": rel, "sha256": digest})
            hasher.update(rel.encode("utf-8") + b"\0" + data + b"\0")
        return records, "sha256:" + hasher.hexdigest()

    def _append_event(self, event: Mapping[str, Any]) -> None:
        self.migration_history()  # never extend a corrupt audit log
        validated = self._validate_migration_event(dict(event), lineno=0, registry=self.registry)
        prior = self.events.read_bytes() if self.events.exists() else b""
        atomic_write_bytes(self.events, prior + _canonical_json(validated) + b"\n")

    def migrate(self) -> dict[str, Any]:
        status = self.inspect()
        if status["current"] and status.get("implicit_empty"):
            marker = {
                "runtime_layout_version": RUNTIME_LAYOUT_VERSION,
                "initialized_at": _utc_now(),
                "initialized_from_empty": True,
            }
            atomic_write_text(self.marker, json.dumps(marker, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            event = {
                "event_schema_version": "1.0.0",
                "event_id": f"migration-{uuid.uuid4()}",
                "recorded_at": _utc_now(),
                "from_version": None,
                "to_version": RUNTIME_LAYOUT_VERSION,
                "action": "initialized_runtime_layout",
                "preserved_file_count": 0,
            }
            self._append_event(event)
            return {
                "changed": True,
                "from_version": None,
                "to_version": RUNTIME_LAYOUT_VERSION,
                "preserved_files": [],
                "event": event,
                "initialized_from_empty": True,
            }
        if status["current"]:
            return {"changed": False, "from_version": status["version"], "to_version": RUNTIME_LAYOUT_VERSION, "preserved_files": []}
        spec = self.registry.get(str(status["version"]), RUNTIME_LAYOUT_VERSION)
        if not spec.preserves_released_evidence:
            raise MigrationError(f"migration {spec.migration_id!r} must explicitly implement evidence transformation")
        records, evidence_digest = self._validate_legacy_evidence()
        marker = {
            "runtime_layout_version": RUNTIME_LAYOUT_VERSION,
            "migrated_from": LEGACY_LAYOUT_VERSION,
            "migration_id": spec.migration_id,
            "migrated_at": _utc_now(),
            "preserved_evidence_digest": evidence_digest,
            "preserved_file_count": len(records),
        }
        atomic_write_text(self.marker, json.dumps(marker, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        event = {
            "event_schema_version": "1.0.0",
            "event_id": f"migration-{uuid.uuid4()}",
            "recorded_at": _utc_now(),
            "from_version": LEGACY_LAYOUT_VERSION,
            "to_version": RUNTIME_LAYOUT_VERSION,
            "migration_id": spec.migration_id,
            "preserved_evidence_digest": evidence_digest,
            "preserved_file_count": len(records),
        }
        self._append_event(event)
        return {
            "changed": True,
            "from_version": LEGACY_LAYOUT_VERSION,
            "to_version": RUNTIME_LAYOUT_VERSION,
            "migration_id": spec.migration_id,
            "preserved_files": records,
            "preserved_evidence_digest": evidence_digest,
            "event": event,
        }


__all__ = [
    "HardeningError",
    "HardeningManager",
    "LEGACY_LAYOUT_VERSION",
    "LockBusyError",
    "MigrationError",
    "MigrationManager",
    "MigrationRegistry",
    "MigrationSpec",
    "RUNTIME_LAYOUT_VERSION",
    "RecoveryRequiredError",
    "TransactionError",
    "after_file_mutation",
    "append_text",
    "atomic_write_bytes",
    "atomic_write_text",
    "before_file_mutation",
]
