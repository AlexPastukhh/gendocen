import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import jsonschema

from docengine.cli import main
from docengine.project import discover_roots
from docengine.hardening import HardeningManager, MigrationManager, RUNTIME_LAYOUT_VERSION, FileTransaction, TransactionError, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "examples/product_tax_project"
SAMPLE = ROOT / "examples/sample_project"
RECOVERY_SCHEMA = json.loads((ROOT / "spec/schemas/HARDENING_RECOVERY_EVENT.schema.json").read_text(encoding="utf-8"))
MIGRATION_SCHEMA = json.loads((ROOT / "spec/schemas/HARDENING_MIGRATION_EVENT.schema.json").read_text(encoding="utf-8"))
LAYOUT_SCHEMA = json.loads((ROOT / "spec/schemas/RUNTIME_LAYOUT.schema.json").read_text(encoding="utf-8"))


def run_json(argv):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(argv)
    return code, json.loads(stream.getvalue())


def core_runtime_snapshot(project: Path):
    dep = project / "docs/_dependency"
    result = {}
    for rel in ("receipts", "baselines", "state", "events"):
        root = dep / rel
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                result[path.relative_to(dep).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class P7MigrationTests(unittest.TestCase):
    def test_p6_unmarked_layout_migrates_without_changing_audit_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            shutil.rmtree(project / "docs/_dependency/hardening", ignore_errors=True)
            before = core_runtime_snapshot(project)
            code, payload = run_json(["migrate", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(payload["meta"]["status"], "migrated")
            self.assertEqual(core_runtime_snapshot(project), before)
            marker = json.loads((project / "docs/_dependency/hardening/runtime_layout.json").read_text(encoding="utf-8"))
            jsonschema.validate(marker, LAYOUT_SCHEMA)
            self.assertEqual(marker["runtime_layout_version"], RUNTIME_LAYOUT_VERSION)
            self.assertEqual(marker["preserved_file_count"], len(before))
            event = json.loads((project / "docs/_dependency/hardening/migration_events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            jsonschema.validate(event, MIGRATION_SCHEMA)

    def test_first_p7_mutation_initializes_layout_in_same_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            code, payload = run_json(["sync", "--all", "--project-root", str(project), "--json"])
            self.assertEqual(code, 2)
            self.assertTrue(payload["ok"])
            marker = json.loads((project / "docs/_dependency/hardening/runtime_layout.json").read_text(encoding="utf-8"))
            self.assertTrue(marker["initialized_from_empty"])
            jsonschema.validate(marker, LAYOUT_SCHEMA)

    def test_materialization_only_p6_runtime_is_migrated_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            dep = project / "docs/_dependency"
            # Simulate a P6 project that only retained materialization provenance.
            shutil.rmtree(dep / "hardening", ignore_errors=True)
            shutil.rmtree(dep / "receipts", ignore_errors=True)
            shutil.rmtree(dep / "baselines", ignore_errors=True)
            shutil.rmtree(dep / "events", ignore_errors=True)
            state = dep / "state"
            (state / "dependency_state.json").unlink(missing_ok=True)
            materialization = state / "materialization_state.json"
            before = hashlib.sha256(materialization.read_bytes()).hexdigest()
            code, payload = run_json(["migrate", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(payload["data"]["from_version"], "legacy-p6-unmarked")
            self.assertEqual(payload["data"]["preserved_files"][0]["path"], "state/materialization_state.json")
            self.assertEqual(hashlib.sha256(materialization.read_bytes()).hexdigest(), before)

    def test_runtime_layout_parser_rejects_schema_invalid_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            marker = project / "docs/_dependency/hardening/runtime_layout.json"
            marker.write_text(json.dumps({
                "runtime_layout_version": "1.0.0",
                "migrated_from": "legacy-p6-unmarked",
                "migration_id": "p6-unmarked-to-runtime-layout-1",
                "migrated_at": "2026-01-01T00:00:00Z",
                "preserved_evidence_digest": "not-a-digest",
                "preserved_file_count": "6",
            }) + "\n")
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            codes = {f["code"] for f in payload["data"]["report"]["findings"]}
            self.assertIn("hardening_runtime_unavailable", codes)

    def test_unknown_runtime_layout_is_never_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            marker = project / "docs/_dependency/hardening/runtime_layout.json"
            marker.write_text(json.dumps({"runtime_layout_version": "9.9.9"}) + "\n")
            before = core_runtime_snapshot(project)
            code, payload = run_json(["migrate", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "migration_failed")
            self.assertEqual(core_runtime_snapshot(project), before)


class P7CrashRecoveryTests(unittest.TestCase):
    def test_hard_crash_mid_rebuild_rolls_back_and_records_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            source = project / "docs/_structured/catalog/product.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            data["data"]["price"] = 177
            source.write_text(json.dumps(data, indent=2) + "\n")
            before = core_runtime_snapshot(project)

            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            env["DOCENGINE_TEST_CRASH_AFTER_WRITES"] = "4"
            proc = subprocess.run(
                [sys.executable, "-m", "docengine.cli", "rebuild", "resource://catalog/price_with_tax", "--project-root", str(project), "--json"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(proc.returncode, 91, (proc.stdout, proc.stderr))
            tx_root = project / "docs/_dependency/hardening/transactions"
            self.assertTrue(any(tx_root.iterdir()))

            code, status = run_json(["status", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(status["meta"]["status"], "recovery_required")

            code, verified = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            finding_codes = {f["code"] for f in verified["data"]["report"]["findings"]}
            self.assertIn("recovery_required", finding_codes)

            code, recovered = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(recovered["data"]["remaining"], 0)
            self.assertEqual(core_runtime_snapshot(project), before)
            event_path = project / "docs/_dependency/hardening/recovery_events.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[-1])
            jsonschema.validate(event, RECOVERY_SCHEMA)
            self.assertEqual(event["action"], "rolled_back_interrupted_transaction")

            code, after = run_json(["verify", "--project-root", str(project), "--json"])
            # Source edit remains, so verification may fail on build-required evidence;
            # the persisted dependency integrity itself must be coherent again.
            self.assertIn(code, {2, 3})
            self.assertTrue(after["data"]["report"]["sections"]["dependency_integrity"]["ok"])


    def test_recovery_refuses_to_overwrite_unknown_post_crash_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            target = project / "docs/catalog/product.md"
            original = target.read_text(encoding="utf-8")
            script = (
                "from pathlib import Path; import os; "
                "from docengine.project import discover_roots; "
                "from docengine.hardening import HardeningManager, FileTransaction, atomic_write_text; "
                "project=Path(os.environ['P7_PROJECT']); roots=discover_roots(project_root=project); "
                "manager=HardeningManager(roots); ctx=manager.lock_manager.held(shared=False); ctx.__enter__(); "
                "tx=FileTransaction(roots,'crash_generated_view'); tx.__enter__(); "
                "atomic_write_text(project/'docs/catalog/product.md','# transaction write\\n')"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            env["P7_PROJECT"] = str(project)
            env["DOCENGINE_TEST_CRASH_AFTER_WRITES"] = "1"
            proc = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env)
            self.assertEqual(proc.returncode, 91)
            target.write_text("# external edit after crash\n", encoding="utf-8")
            code, payload = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "recovery_required")
            self.assertEqual(target.read_text(encoding="utf-8"), "# external edit after crash\n")
            self.assertNotEqual(target.read_text(encoding="utf-8"), original)
            code, forced = run_json(["recover", "--force", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            event = json.loads((project / "docs/_dependency/hardening/recovery_events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertTrue(event["forced"])
            self.assertIn("catalog/product.md", event["conflict_paths"])
            jsonschema.validate(event, RECOVERY_SCHEMA)


    def test_committed_leftover_is_readable_cleanup_warning_not_recovery_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            txid = "txn-00000000-0000-0000-0000-000000000001"
            txdir = project / "docs/_dependency/hardening/transactions" / txid
            txdir.mkdir(parents=True)
            journal = {
                "journal_schema_version": "1.0.0",
                "transaction_id": txid,
                "operation": "rebuild",
                "phase": "committed",
                "started_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:01Z",
                "operations": [],
            }
            (txdir / "journal.json").write_text(json.dumps(journal) + "\n")
            code, status = run_json(["status", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(status["ok"])
            code, verified = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            warnings = {x["code"] for x in verified["data"]["report"]["findings"] if x["severity"] == "warning"}
            self.assertIn("transaction_cleanup_required", warnings)
            code, recovered = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertFalse(txdir.exists())
            self.assertEqual(recovered["data"]["remaining"], 0)

class P7LockingTests(unittest.TestCase):
    def _holder(self, project: Path, shared: bool, ready: Path):
        script = (
            "from pathlib import Path; import time; "
            "from docengine.project import discover_roots; from docengine.hardening import HardeningManager; "
            f"r=discover_roots(project_root={str(project)!r}); m=HardeningManager(r); "
            f"ctx=m.lock_manager.held(shared={shared!r}); lock=ctx.__enter__(); "
            f"Path({str(ready)!r}).write_text('ready'); time.sleep(30)"
        )
        env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.Popen([sys.executable, "-c", script], cwd=ROOT, env=env)

    @staticmethod
    def _wait_ready(path: Path):
        deadline = time.time() + 5
        while time.time() < deadline:
            if path.exists(): return
            time.sleep(0.02)
        raise AssertionError("lock holder did not become ready")

    def test_writer_conflict_is_rejected_and_reader_never_observes_partial_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; shutil.copytree(PRODUCT, project)
            ready = Path(tmp) / "ready"
            holder = self._holder(project, False, ready)
            try:
                self._wait_ready(ready)
                for command in (["check"], ["status"]):
                    with self.subTest(command=command):
                        code, payload = run_json([*command, "--project-root", str(project), "--json"])
                        self.assertEqual(code, 3)
                        self.assertEqual(payload["meta"]["status"], "runtime_busy")
            finally:
                holder.terminate(); holder.wait(timeout=5)

    @unittest.skipIf(os.name == "nt", "Windows v0.1 safely serializes readers; shared-reader parity is POSIX-only")
    def test_concurrent_readers_share_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; shutil.copytree(PRODUCT, project)
            ready = Path(tmp) / "ready"
            holder = self._holder(project, True, ready)
            try:
                self._wait_ready(ready)
                code, payload = run_json(["status", "--project-root", str(project), "--json"])
                self.assertEqual(code, 0)
                self.assertTrue(payload["ok"])
            finally:
                holder.terminate(); holder.wait(timeout=5)

    @unittest.skipUnless(os.name == "nt", "Windows-specific safe serialization contract")
    def test_windows_concurrent_readers_serialize_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; shutil.copytree(PRODUCT, project)
            ready = Path(tmp) / "ready"
            holder = self._holder(project, True, ready)
            try:
                self._wait_ready(ready)
                code, payload = run_json(["status", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3)
                self.assertEqual(payload["meta"]["status"], "runtime_busy")
            finally:
                holder.terminate(); holder.wait(timeout=5)

    def test_external_lock_does_not_mutate_project_for_read_only_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; (project / "docs").mkdir(parents=True); (project / "docs/readme.md").write_text("# docs\n")
            before = sorted(p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file())
            code, _ = run_json(["resources", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            after = sorted(p.relative_to(project).as_posix() for p in project.rglob("*") if p.is_file())
            self.assertEqual(after, before)


class P7HardeningPathTests(unittest.TestCase):
    def test_hardening_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"; shutil.copytree(PRODUCT, project)
            hardening = project / "docs/_dependency/hardening"
            shutil.rmtree(hardening)
            redirected = project / "docs/redirected_hardening"; redirected.mkdir()
            hardening.symlink_to(redirected, target_is_directory=True)
            code, payload = run_json(["status", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "hardening_failure")




class P7CanonicalPathIdentityTests(unittest.TestCase):
    def test_transaction_relative_path_uses_resolved_root_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            roots = discover_roots(project_root=project)
            alias_component = project / "lexical-alias"
            alias_component.mkdir()
            # `lexical-alias/../docs` resolves to the same physical directory as
            # `docs`, but is not a lexical prefix of the canonical target path.
            # This models Windows long-name/8.3 alias disagreement without
            # requiring platform-specific filesystem configuration.
            aliased_docs = alias_component / ".." / "docs"
            from dataclasses import replace
            aliased_roots = replace(roots, documentation_root=aliased_docs)
            tx = FileTransaction(aliased_roots, "canonical_path_identity_probe")
            target = roots.documentation_root / "catalog/product.md"
            self.assertEqual(tx._relative(target), "catalog/product.md")


class P7PostAxisRegressionTests(unittest.TestCase):
    def test_semantically_impossible_new_file_journal_cannot_delete_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            target = project / "docs/catalog/product.md"
            before = target.read_bytes()
            txid = "txn-00000000-0000-4000-8000-000000000099"
            txdir = project / "docs/_dependency/hardening/transactions" / txid
            txdir.mkdir(parents=True)
            journal = {
                "journal_schema_version": "1.0.0",
                "transaction_id": txid,
                "operation": "rebuild",
                "phase": "open",
                "started_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:01Z",
                "operations": [{
                    "path": "catalog/product.md",
                    "existed": False,
                    "backup": None,
                    "before_hash": None,
                    "planned_after_hashes": [],
                }],
            }
            (txdir / "journal.json").write_text(json.dumps(journal) + "\n", encoding="utf-8")
            code, payload = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "recovery_required")
            self.assertEqual(target.read_bytes(), before)
            self.assertTrue(txdir.exists())

    def test_failed_synchronous_rollback_preserves_journal_for_later_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            roots = discover_roots(project_root=project)
            target = project / "docs/catalog/product.md"
            original = target.read_bytes()
            tx = None
            with self.assertRaises(TransactionError):
                with FileTransaction(roots, "rollback_failure_probe") as tx:
                    atomic_write_text(target, "# mutated\n")
                    op = next(iter(tx._ops.values()))
                    (tx.path / op["backup"]).unlink()
                    raise RuntimeError("force rollback")
            self.assertNotEqual(target.read_bytes(), original)
            self.assertIsNotNone(tx)
            self.assertTrue(tx.path.exists())
            pending = HardeningManager(roots).pending_transactions()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["phase"], "open")
            code, payload = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "recovery_required")
            self.assertTrue(tx.path.exists())

    def test_rogue_transaction_entries_are_corruption_not_silently_ignored(self):
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(PRODUCT, project)
                txroot = project / "docs/_dependency/hardening/transactions"
                txroot.mkdir(parents=True, exist_ok=True)
                rogue = txroot / "txn-rogue"
                if kind == "file":
                    rogue.write_text("corrupt", encoding="utf-8")
                else:
                    redirected = project / "docs/rogue-transaction-target"
                    redirected.mkdir()
                    rogue.symlink_to(redirected, target_is_directory=True)
                code, payload = run_json(["status", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3)
                self.assertEqual(payload["meta"]["status"], "recovery_required")
                code, verified = run_json(["verify", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3)
                self.assertEqual(verified["meta"]["status"], "verification_failed")
                self.assertTrue(any(x["code"] == "recovery_required" for x in verified["data"]["report"]["findings"]))

    def test_external_deletion_after_crash_requires_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            target = project / "docs/catalog/product.md"
            original = target.read_bytes()
            script = (
                "from pathlib import Path; import os; "
                "from docengine.project import discover_roots; "
                "from docengine.hardening import HardeningManager, FileTransaction, atomic_write_text; "
                "project=Path(os.environ['P7_PROJECT']); roots=discover_roots(project_root=project); "
                "manager=HardeningManager(roots); ctx=manager.lock_manager.held(shared=False); ctx.__enter__(); "
                "tx=FileTransaction(roots,'external_delete_probe'); tx.__enter__(); "
                "atomic_write_text(project/'docs/catalog/product.md','# transaction write\\n')"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            env["P7_PROJECT"] = str(project)
            env["DOCENGINE_TEST_CRASH_AFTER_WRITES"] = "1"
            proc = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env)
            self.assertEqual(proc.returncode, 91)
            target.unlink()
            code, payload = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "recovery_required")
            self.assertFalse(target.exists())
            code, forced = run_json(["recover", "--force", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), original)
            event = json.loads((project / "docs/_dependency/hardening/recovery_events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertTrue(event["forced"])
            self.assertIn("catalog/product.md", event["conflict_paths"])

    def test_runtime_layout_schema_and_registry_provenance_match_runtime(self):
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"runtime_layout_version": "1.0.0"}, LAYOUT_SCHEMA)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            marker = project / "docs/_dependency/hardening/runtime_layout.json"
            data = json.loads(marker.read_text(encoding="utf-8"))
            data["migrated_from"] = "unknown-layout"
            data["migration_id"] = "fake-migration"
            marker.write_text(json.dumps(data, indent=2) + "\n")
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "verification_failed")
            self.assertTrue(any(x["code"] == "hardening_runtime_unavailable" for x in payload["data"]["report"]["findings"]))

    def test_migration_rejects_symlinked_or_corrupt_released_evidence(self):
        for kind in ("symlink", "tampered_hash"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(PRODUCT, project)
                shutil.rmtree(project / "docs/_dependency/hardening", ignore_errors=True)
                receipt = next((project / "docs/_dependency/receipts").glob("receipt-*.json"))
                if kind == "symlink":
                    outside = project / "receipt-copy.json"
                    outside.write_bytes(receipt.read_bytes())
                    receipt.unlink()
                    receipt.symlink_to(outside)
                else:
                    data = json.loads(receipt.read_text(encoding="utf-8"))
                    data["receipt_hash"] = "sha256:" + "0" * 64
                    receipt.write_text(json.dumps(data, indent=2) + "\n")
                code, payload = run_json(["migrate", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3)
                self.assertEqual(payload["meta"]["status"], "migration_failed")
                self.assertFalse((project / "docs/_dependency/hardening/runtime_layout.json").exists())

    def test_verify_corrupt_receipt_remains_complete_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            receipt = next((project / "docs/_dependency/receipts").glob("receipt-*.json"))
            data = json.loads(receipt.read_text(encoding="utf-8"))
            data["receipt_hash"] = "sha256:" + "0" * 64
            receipt.write_text(json.dumps(data, indent=2) + "\n")
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "verification_failed")
            self.assertIn("report", payload["data"])
            codes = {x["code"] for x in payload["data"]["report"]["findings"]}
            self.assertTrue({"receipt_store_invalid", "active_receipts_unreadable"} & codes)

    def test_verify_detects_corrupt_hardening_audit_logs(self):
        for name in ("migration_events.jsonl", "recovery_events.jsonl"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(PRODUCT, project)
                log = project / "docs/_dependency/hardening" / name
                log.write_text("{not-json}\n", encoding="utf-8")
                code, payload = run_json(["verify", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3)
                self.assertEqual(payload["meta"]["status"], "verification_failed")
                self.assertTrue(any(x["code"] == "hardening_runtime_unavailable" for x in payload["data"]["report"]["findings"]))

    def test_transaction_id_mismatch_is_corruption_not_path_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            txid = "txn-00000000-0000-4000-8000-000000000077"
            txdir = project / "docs/_dependency/hardening/transactions" / txid
            txdir.mkdir(parents=True)
            journal = {
                "journal_schema_version": "1.0.0",
                "transaction_id": "txn-00000000-0000-4000-8000-000000000078",
                "operation": "rebuild",
                "phase": "open",
                "started_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:01Z",
                "operations": [],
            }
            (txdir / "journal.json").write_text(json.dumps(journal) + "\n")
            code, payload = run_json(["recover", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(payload["meta"]["status"], "recovery_required")
            self.assertTrue(txdir.exists())

class P7BenchmarkToolTests(unittest.TestCase):
    def test_small_benchmark_smoke(self):
        env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'src')
        proc=subprocess.run([sys.executable, str(ROOT/'tools/benchmark_p7.py'), '--targets','1000','--edges','5000','--json'], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        data=json.loads(proc.stdout)
        self.assertEqual(data['targets'],1000)
        self.assertEqual(data['edges'],5000)
        self.assertEqual(data['edge_count_reported'],5000)
        self.assertEqual(data['acceptance_budget_status'],'baseline_only_p7_budget_deferred_to_p8')


if __name__ == "__main__":
    unittest.main()
