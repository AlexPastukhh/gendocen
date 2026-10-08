"""Crash boundaries, maintenance authority and legacy recovery for P-1."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

import jsonschema
import pytest

from docengine import hardening as h
from docengine.cli import main
from docengine.project import discover_roots

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "project"
    shutil.copytree(ROOT / "examples/product_tax_project", path)
    return path


def command(project, name):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main([name, "--project-root", str(project), "--json"])
    return code, json.loads(out.getvalue())


def manager(project):
    return h.HardeningManager(discover_roots(project_root=project))


def assert_retry(project):
    m = manager(project)
    with m.read_guard():
        pass
    result = m.recover()
    assert result["remaining"] == 0
    assert m.recover()["remaining"] == 0
    assert command(project, "check")[0] in (0, 2)
    assert not m.pending_transactions()


@pytest.mark.parametrize("boundary", ["before_journal", "after_journal", "before_activation", "after_activation"])
def test_preparation_failure_is_retryable_and_never_changes_targets(project, boundary):
    m = manager(project)
    target = project / "docs/probe.md"
    target.write_bytes(b"before\n")
    method = "_write_journal" if "journal" in boundary else "_activate"
    original = getattr(h.FileTransaction, method)
    def fail(self, *args):
        if boundary.startswith("after"):
            original(self, *args)
        raise OSError("injected preparation interruption")
    with mock.patch.object(h.FileTransaction, method, fail), pytest.raises(OSError):
        with h.FileTransaction(m.roots, "probe"):
            h.atomic_write_text(target, "must not be written\n")
    assert target.read_bytes() == b"before\n"
    assert h.active_transaction() is None
    assert all(x["phase"] != "corrupt" for x in m.pending_transactions())
    if boundary == "after_activation":
        with pytest.raises(h.RecoveryRequiredError):
            with m.read_guard():
                pass
        m.recover()
    assert_retry(project)


@pytest.mark.parametrize("outcome", ["committed", "rollback", "recover"])
@pytest.mark.parametrize("boundary", ["before_ticket", "after_ticket", "before_move", "after_move", "partial_delete", "after_payload_delete"])
def test_retirement_interruption_preserves_completed_bytes_and_retries(project, outcome, boundary):
    m = manager(project)
    target = project / "docs/probe.md"
    target.write_bytes(b"before\n")
    created = project / "docs/created.md"
    original_publish = h.HardeningManager._publish_cleanup_ticket
    original_move = h.HardeningManager._move_to_cleanup
    original_remove = h.shutil.rmtree
    def publish(self, *args):
        if boundary == "before_ticket":
            raise OSError("before ticket")
        value = original_publish(self, *args)
        if boundary == "after_ticket":
            raise OSError("after ticket")
        return value
    def move(self, *args):
        if boundary == "before_move":
            raise OSError("before move")
        value = original_move(self, *args)
        if boundary == "after_move":
            raise OSError("after move")
        return value
    def remove(path, *args, **kwargs):
        path = Path(path)
        if path.parent == m.cleanup_root:
            if boundary == "partial_delete":
                (path / "journal.json").unlink()
                raise OSError("journal deleted, payload directory remains")
            if boundary == "after_payload_delete":
                original_remove(path, *args, **kwargs)
                raise OSError("payload deleted, external ticket remains")
        return original_remove(path, *args, **kwargs)
    tx = h.FileTransaction(m.roots, "probe")
    tx.__enter__()
    h.atomic_write_text(target, "after\n")
    h.atomic_write_text(created, "created\n")
    with mock.patch.object(h.HardeningManager, "_publish_cleanup_ticket", publish), mock.patch.object(h.HardeningManager, "_move_to_cleanup", move), mock.patch.object(h.shutil, "rmtree", remove), pytest.raises(OSError):
        if outcome == "recover":
            h._ACTIVE_TRANSACTION.reset(tx._token)
            m.recover()
        else:
            tx.__exit__(None if outcome == "committed" else RuntimeError, None, None)
    expected = b"after\n" if outcome == "committed" else b"before\n"
    assert target.read_bytes() == expected
    assert created.exists() == (outcome == "committed")
    assert h.active_transaction() is None
    records = m.pending_transactions()
    assert records and all(x["phase"] != "corrupt" for x in records)
    # Without the completion ticket, rolled-back active evidence is recoverable.
    if outcome != "committed" and boundary == "before_ticket":
        m.recover()
    else:
        # Read-only maintenance diagnostics may not change a single byte.
        before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        assert command(project, "status")[0] == 0
        after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        assert after == before
    assert_retry(project)
    assert target.read_bytes() == expected
    assert created.exists() == (outcome == "committed")


@pytest.mark.parametrize("area,kind", [
    ("active", "empty"), ("preparation", "rogue"), ("preparation", "bad_journal"),
    ("cleanup", "missing_ticket"), ("cleanup", "invalid_ticket"),
    ("cleanup", "unknown_file"), ("cleanup", "hash_mismatch"), ("cleanup", "identity_conflict"),
])
def test_unknown_or_corrupt_lifecycle_evidence_is_preserved(project, area, kind):
    m = manager(project)
    txid = "txn-00000000-0000-4000-8000-000000000071"
    root = {"active": m.tx_root, "preparation": m.preparation_root, "cleanup": m.cleanup_root}[area]
    directory = root / txid
    directory.mkdir(parents=True)
    if kind == "rogue":
        (directory / "unknown.bin").write_bytes(b"do not discard")
    elif kind == "bad_journal":
        (directory / "journal.json").write_text("{}")
    elif kind == "invalid_ticket":
        (root / (txid + ".json")).write_text("{}")
    elif kind == "unknown_file":
        (root / "unknown.json").write_text("{}")
    elif kind in {"hash_mismatch", "identity_conflict"}:
        active = m.tx_root / txid
        active.mkdir(parents=True, exist_ok=True)
        journal = dict(journal_schema_version="1.0.0", transaction_id=txid, operation="probe", phase="committed", started_at=h._utc_now(), updated_at=h._utc_now(), operations=[])
        (active / "journal.json").write_bytes(h._canonical_json(journal))
        ticket = m._publish_cleanup_ticket(active, "committed")
        if kind == "hash_mismatch":
            directory.rmdir()
            (active / "journal.json").write_bytes(h._canonical_json({**journal, "operation": "tampered"}))
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert any(x["phase"] == "corrupt" for x in m.pending_transactions())
    with pytest.raises(h.RecoveryRequiredError):
        m.recover()
    assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    assert directory.exists() if kind != "hash_mismatch" else (m.tx_root / txid).exists()


def test_recognized_incomplete_metadata_temps_are_disposable(project):
    m = manager(project)
    txid = "txn-00000000-0000-4000-8000-000000000073"
    prep = m.preparation_root / txid
    prep.mkdir(parents=True)
    (prep / "journal.json.tmp-12-abcdef01").write_bytes(b"incomplete")
    m.cleanup_root.mkdir()
    (m.cleanup_root / (txid + ".json.tmp-12-abcdef01")).write_bytes(b"incomplete")
    assert all(x["cleanup_only"] for x in m.pending_transactions())
    assert_retry(project)


def test_target_write_requires_activation(project):
    tx = h.FileTransaction(manager(project).roots, "probe")
    with pytest.raises(h.TransactionError):
        tx.before_write(project / "docs/probe.md")


def test_activation_never_replaces_an_existing_empty_active_directory(project):
    m = manager(project)
    tx = h.FileTransaction(m.roots, "probe")
    existing = m.tx_root / tx.transaction_id
    existing.mkdir(parents=True)
    with pytest.raises(h.TransactionError):
        tx.__enter__()
    assert existing.is_dir() and not list(existing.iterdir())
    assert h.active_transaction() is None
    with pytest.raises(h.RecoveryRequiredError):
        m.recover()
    assert existing.exists()


@pytest.mark.parametrize("failure", ["first_journal", "journal_removed_during_cleanup"])
def test_original_cli_blockers_now_allow_next_check_and_recover(project, failure):
    if failure == "first_journal":
        patch = mock.patch.object(h.FileTransaction, "_write_journal", side_effect=OSError("initial journal failed"))
    else:
        original = h.shutil.rmtree
        def interrupt(path, *args, **kwargs):
            path = Path(path)
            if path.parent.name == "transaction_cleanup":
                (path / "journal.json").unlink()
                raise OSError("cleanup interrupted after journal removal")
            return original(path, *args, **kwargs)
        patch = mock.patch.object(h.shutil, "rmtree", interrupt)
    with patch:
        assert command(project, "check")[0] == 5
    assert command(project, "check")[0] in (0, 2)
    assert command(project, "recover")[0] == 0
    assert not manager(project).pending_transactions()


def test_cleanup_ticket_schema_matches_runtime(project):
    m = manager(project)
    with mock.patch.object(h.HardeningManager, "_finish_cleanup", side_effect=OSError("pause")), pytest.raises(OSError):
        with h.FileTransaction(m.roots, "probe"):
            pass
    ticket_path = next(m.cleanup_root.glob("*.json"))
    schema = json.loads((ROOT / "spec/schemas/TRANSACTION_CLEANUP.schema.json").read_text())
    jsonschema.validate(json.loads(ticket_path.read_text()), schema)
    assert_retry(project)


@pytest.mark.parametrize("field,value", [("outcome", []), ("outcome", {}), ("journal_hash", 7), ("completed_at", False), ("transaction_id", None), ("cleanup_schema_version", "9.0.0")])
def test_malformed_ticket_fields_remain_domain_corruption(project, field, value):
    m = manager(project)
    with mock.patch.object(h.HardeningManager, "_finish_cleanup", side_effect=OSError("pause")), pytest.raises(OSError):
        with h.FileTransaction(m.roots, "probe"):
            pass
    path = next(m.cleanup_root.glob("*.json"))
    ticket = json.loads(path.read_text())
    ticket[field] = value
    path.write_text(json.dumps(ticket))
    assert any(item["phase"] == "corrupt" for item in m.pending_transactions())
    assert command(project, "recover")[0] == 3
    assert path.exists()


@pytest.mark.parametrize("area", ["preparation_root", "cleanup_root", "preparation_child", "cleanup_ticket", "cleanup_child"])
@pytest.mark.requires_symlink
def test_lifecycle_symlinks_are_rejected_without_touching_destination(project, tmp_path, area):
    m = manager(project)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"outside must stay intact")
    txid = "txn-00000000-0000-4000-8000-000000000079"
    if area.endswith("_root"):
        link = getattr(m, area)
        dest = outside
    elif area == "preparation_child":
        directory = m.preparation_root / txid
        directory.mkdir(parents=True)
        link, dest = directory / "journal.json.tmp-12-abcdef01", sentinel
    else:
        with mock.patch.object(h.HardeningManager, "_finish_cleanup", side_effect=OSError("pause")), pytest.raises(OSError):
            with h.FileTransaction(m.roots, "probe"):
                pass
        link = next(m.cleanup_root.glob("*.json")) if area == "cleanup_ticket" else next(p for p in m.cleanup_root.iterdir() if p.is_dir()) / "journal.json"
        link.unlink()
        dest = sentinel
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(dest, target_is_directory=dest.is_dir())
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows execution context cannot create symlinks (WinError 1314)")
        raise
    with pytest.raises(h.HardeningError):
        m.recover()
    assert sentinel.read_bytes() == b"outside must stay intact"
    assert link.is_symlink()


@pytest.mark.parametrize("boundary", [
    "before_journal", "after_journal", "journal_temporary", "before_activation", "after_activation", "open_write",
    "commit_mark", "ticket_temporary", "after_ticket", "after_move", "partial_delete", "after_payload_delete",
    "rollback_after_ticket", "recover_after_ticket",
])
def test_hard_process_exit_at_lifecycle_boundaries(project, boundary):
    script = f'''
import os
from pathlib import Path
from docengine import hardening as h
from docengine.project import discover_roots
project = Path({str(project)!r})
boundary = {boundary!r}
m = h.HardeningManager(discover_roots(project_root=project))
target = project / 'docs/probe.md'
target.write_bytes(b'before\\n')
stop = lambda: os._exit(92)
old_journal = h.FileTransaction._write_journal
def journal(self, phase):
    if boundary == 'before_journal': stop()
    old_journal(self, phase)
    if boundary == 'after_journal' or (boundary == 'commit_mark' and phase == 'committed'): stop()
h.FileTransaction._write_journal = journal
old_atomic = h._direct_atomic_write
def atomic(path, data):
    match = (boundary == 'journal_temporary' and path.name == 'journal.json') or (boundary == 'ticket_temporary' and path.parent == m.cleanup_root)
    if match:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_name(path.name + '.tmp-123-abcdef01').write_bytes(b'incomplete')
        stop()
    old_atomic(path, data)
h._direct_atomic_write = atomic
old_activate = h.FileTransaction._activate
def activate(self):
    if boundary == 'before_activation': stop()
    old_activate(self)
    if boundary == 'after_activation': stop()
h.FileTransaction._activate = activate
old_publish = h.HardeningManager._publish_cleanup_ticket
def publish(self, *args):
    value = old_publish(self, *args)
    if boundary in ('after_ticket', 'rollback_after_ticket', 'recover_after_ticket'): stop()
    return value
h.HardeningManager._publish_cleanup_ticket = publish
old_move = h.HardeningManager._move_to_cleanup
def move(self, *args):
    value = old_move(self, *args)
    if boundary == 'after_move': stop()
    return value
h.HardeningManager._move_to_cleanup = move
old_remove = h.shutil.rmtree
def remove(path, *args, **kwargs):
    path = Path(path)
    if path.parent == m.cleanup_root and boundary == 'partial_delete':
        (path / 'journal.json').unlink()
        stop()
    value = old_remove(path, *args, **kwargs)
    if path.parent == m.cleanup_root and boundary == 'after_payload_delete': stop()
    return value
h.shutil.rmtree = remove
tx = h.FileTransaction(m.roots, 'probe')
tx.__enter__()
h.atomic_write_text(target, 'after\\n')
if boundary == 'open_write': stop()
if boundary == 'recover_after_ticket':
    h._ACTIVE_TRANSACTION.reset(tx._token)
    m.recover()
elif boundary == 'rollback_after_ticket':
    tx.__exit__(RuntimeError, RuntimeError('rollback'), None)
else:
    tx.__exit__(None, None, None)
raise AssertionError('crash point not reached')
'''
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / 'src')
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 92, result.stdout + result.stderr
    m = manager(project)
    assert m.pending_transactions()
    assert all(x['phase'] != 'corrupt' for x in m.pending_transactions())
    m.recover()
    committed = boundary in {'commit_mark', 'ticket_temporary', 'after_ticket', 'after_move', 'partial_delete', 'after_payload_delete'}
    assert (project / 'docs/probe.md').read_bytes() == (b'after\n' if committed else b'before\n')
    assert_retry(project)
