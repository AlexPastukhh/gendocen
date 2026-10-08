import pytest
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docengine.builders import BuildEngine
from docengine.cli import main
from docengine.dependencies import DependencyRuntime
from docengine.extensions import load_project_extension
from docengine.materialization import MaterializationError, MaterializationRuntime, MaterializationStateStore, SyncRuntime
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "examples/product_tax_project"
SAMPLE = ROOT / "examples/sample_project"


def fresh_copy(source: Path, tmp: str) -> Path:
    project = Path(tmp) / "project"
    shutil.copytree(source, project)
    shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
    return project


def p5_runtime(project: Path):
    roots = discover_roots(project_root=project)
    catalog = ResourceCatalog.scan(roots)
    extension = load_project_extension(roots, catalog)
    dependency = DependencyRuntime(
        roots,
        catalog,
        extension.registry,
        semantic_rule_revisions=extension.semantic_registry.revisions_by_target(),
    )
    materialization = MaterializationRuntime(
        roots, catalog, extension.registry, extension.renderer_registry, dependency
    )
    sync = SyncRuntime(dependency, extension.semantic_registry, materialization)
    return roots, catalog, extension, dependency, materialization, sync


class P5MaterializationTests(unittest.TestCase):
    def test_deleted_managed_markdown_is_deterministically_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            first = materialization.materialize(all_targets=True)
            product_md = project / "docs/catalog/product.md"
            expected = product_md.read_bytes()
            self.assertIn(b"# Product", expected)
            self.assertIn(b"**Price:** 100", expected)
            product_md.unlink()
            self.assertTrue(materialization.inspect()["drifted"] >= 1)
            second = materialization.materialize("resource://catalog/product")
            self.assertEqual(product_md.read_bytes(), expected)
            self.assertEqual(second["written"], 1)
            third = materialization.materialize("resource://catalog/product")
            self.assertEqual(third["written"], 0)
            self.assertFalse(third["state_changed"])

    def test_derived_markdown_is_recreated_from_builder_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            path = project / "docs/catalog/price_with_tax.md"
            path.unlink(missing_ok=True)
            result = materialization.materialize("resource://catalog/price_with_tax")
            text = path.read_text(encoding="utf-8")
            self.assertIn("# Price with tax", text)
            self.assertIn("**Total:** 120.0", text)
            self.assertEqual(result["after"]["drifted"], 0)

    def test_manual_generated_drift_is_detected_and_clean_regeneration_repairs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            materialization.materialize(all_targets=True)
            path = project / "docs/catalog/tax_policy.md"
            canonical = path.read_bytes()
            path.write_text("# Hand edited\n", encoding="utf-8")
            inspection = materialization.inspect()
            drift = next(x for x in inspection["outputs"] if x["path"] == "catalog/tax_policy.md")
            self.assertTrue(drift["drift"])
            self.assertEqual(drift["state"], "drifted")
            repaired = materialization.materialize(all_targets=True)
            self.assertEqual(path.read_bytes(), canonical)
            self.assertGreaterEqual(repaired["written"], 1)
            self.assertEqual(repaired["after"]["drifted"], 0)

    def test_unregistered_plain_file_is_never_a_materialization_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            plain = project / "docs/manual.md"
            plain.write_text("# Manual canonical file\n", encoding="utf-8")
            _, _, _, _, materialization, _ = p5_runtime(project)
            with self.assertRaisesRegex(MaterializationError, "not a registered materialization target"):
                materialization.materialize("file://manual.md")
            self.assertEqual(plain.read_text(encoding="utf-8"), "# Manual canonical file\n")

    @pytest.mark.requires_symlink
    def test_materialization_refuses_symlink_replacement_after_catalog_scan(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, _ = p5_runtime(project)
            target = project / "docs/catalog/product.md"
            target.unlink(missing_ok=True)
            outside = Path(outside_tmp) / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            target.symlink_to(outside)
            with self.assertRaisesRegex(MaterializationError, "symlink|escapes configured root"):
                materialization.materialize("resource://catalog/product")
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside")


class P5SyncTests(unittest.TestCase):
    def test_affected_only_sync_rebuilds_and_materializes_only_changed_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, _, sync = p5_runtime(project)
            initial = sync.sync(all_targets=True)
            self.assertTrue(initial["ok"])
            self.assertEqual(initial["status"], "ok")
            self.assertEqual(len(initial["rebuilt"]), 1)
            # Canonical bundled example views may already match byte-for-byte; initial
            # sync must register provenance without gratuitously rewriting them.
            self.assertEqual(initial["materialization"]["written"], 0)
            self.assertTrue(initial["materialization"]["state_changed"])

            product_json = project / "docs/_structured/catalog/product.json"
            payload = json.loads(product_json.read_text(encoding="utf-8"))
            payload["data"]["price"] = 150
            product_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            _, _, _, _, _, sync2 = p5_runtime(project)
            changed = sync2.sync()
            self.assertTrue(changed["ok"])
            self.assertEqual([x["target"] for x in changed["rebuilt"]], ["resource://catalog/price_with_tax"])
            paths = {x["path"] for x in changed["materialization"]["results"]}
            self.assertEqual(paths, {"catalog/product.md", "catalog/price_with_tax.md"})
            self.assertNotIn("catalog/tax_policy.md", paths)
            self.assertIn("**Total:** 180.0", (project / "docs/catalog/price_with_tax.md").read_text(encoding="utf-8"))

    def test_repeated_sync_without_changes_has_no_output_or_event_churn(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, dependency, _, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            events_before = len(dependency.events.all())
            state_bytes = (project / "docs/_dependency/state/materialization_state.json").read_bytes()

            _, _, _, dependency2, _, sync2 = p5_runtime(project)
            result = sync2.sync()
            self.assertTrue(result["ok"])
            self.assertEqual(result["rebuilt"], [])
            self.assertEqual(result["materialization"]["results"], [])
            self.assertFalse(result["materialization"]["state_changed"])
            self.assertEqual(len(dependency2.events.all()), events_before)
            self.assertEqual((project / "docs/_dependency/state/materialization_state.json").read_bytes(), state_bytes)

    def test_semantic_target_remains_attention_required_and_content_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(SAMPLE, tmp)
            rationale = project / "docs/architecture/rationale.md"
            before = rationale.read_bytes()
            _, _, _, _, _, sync = p5_runtime(project)
            result = sync.sync(all_targets=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "attention_required")
            self.assertIn("file://architecture/rationale.md", result["attention_targets"])
            self.assertEqual(rationale.read_bytes(), before)

    def test_mixed_semantic_builder_scc_is_bounded_and_reports_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(SAMPLE, tmp)
            builders = project / "docengine_project/builders.py"
            builders.write_text(
                "def build_system_summary(ctx):\n"
                "    title = ctx.read(\"resource://architecture/overview#/title\")\n"
                "    return {\"title\": \"System Summary\", \"overview_title\": title}\n\n"
                "def build_mixed(ctx):\n"
                "    text = ctx.read(\"file://architecture/rationale.md\", comparator=\"text_unified\")\n"
                "    return {\"text\": text}\n\n"
                "def register(registry):\n"
                "    registry.register(\"resource://architecture/system_summary\", build_system_summary, builder_id=\"sample.system_summary\")\n"
                "    registry.register(\"resource://derived/mixed\", build_mixed, builder_id=\"mixed.builder\")\n",
                encoding="utf-8",
            )
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                '''def register(registry):\n'''
                '''    registry.register(\n'''
                '''        "file://architecture/rationale.md",\n'''
                '''        [("resource://derived/mixed#/text", "text_unified")],\n'''
                '''        rule_id="mixed.semantic",\n'''
                '''        dependency_type="semantic_review",\n'''
                '''    )\n''',
                encoding="utf-8",
            )
            _, _, _, _, _, sync = p5_runtime(project)
            first = sync.sync()
            self.assertTrue(first["ok"])
            self.assertEqual(first["status"], "attention_required")
            rebuilt_targets = [x["target"] for x in first["rebuilt"]]
            self.assertIn("resource://derived/mixed", rebuilt_targets)
            self.assertEqual(rebuilt_targets.count("resource://derived/mixed"), 1)
            self.assertEqual(len(first["mixed_sccs"]), 1)
            self.assertIn("file://architecture/rationale.md", first["mixed_sccs"][0]["semantic_members"])
            self.assertIn("resource://derived/mixed", first["mixed_sccs"][0]["builder_members"])

            _, _, _, dependency2, _, sync2 = p5_runtime(project)
            events_before = len(dependency2.events.all())
            second = sync2.sync()
            self.assertTrue(second["ok"])
            self.assertEqual(second["rebuilt"], [])
            self.assertEqual(len(dependency2.events.all()), events_before)


class P5CliTests(unittest.TestCase):
    def test_materialize_rebuild_and_sync_json_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            commands = [
                ["rebuild", "resource://catalog/price_with_tax"],
                ["materialize", "--all"],
                ["sync"],
            ]
            for argv in commands:
                with self.subTest(argv=argv):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        code = main([*argv, "--project-root", str(project), "--json"])
                    self.assertEqual(code, 0, stream.getvalue())
                    payload = json.loads(stream.getvalue())
                    self.assertTrue(payload["ok"])
                    self.assertEqual(payload["command"], argv[0])

    def test_sync_attention_required_is_successful_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(SAMPLE, tmp)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["sync", "--all", "--project-root", str(project), "--json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 2)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["attention_required"])
            self.assertEqual(payload["meta"]["status"], "attention_required")
            self.assertIn("file://architecture/rationale.md", payload["data"]["attention_targets"])

    def test_materialize_unowned_target_stays_in_json_error_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["materialize", "file://manual.md", "--project-root", str(project), "--json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "materialize_failed")


class P5AdditionalMaterializationTests(unittest.TestCase):
    def test_project_renderer_registry_can_materialize_custom_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            descriptor = project / "docs/_structured/catalog/product.json"
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
            payload["$docengine"]["materialize"].append({
                "renderer": "compact",
                "path": "exports/product.txt",
                "path_base": "documentation_root",
            })
            descriptor.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            init = project / "docengine_project/__init__.py"
            init.write_text(
                init.read_text(encoding="utf-8")
                + "\n\ndef register_renderers(registry):\n"
                  "    def compact(value, context):\n"
                  "        return f\"{value['name']}={value['price']}\\n\"\n"
                  "    registry.register(\"compact\", compact)\n",
                encoding="utf-8",
            )
            _, _, _, _, materialization, _ = p5_runtime(project)
            result = materialization.materialize("resource://catalog/product")
            self.assertEqual(
                (project / "docs/exports/product.txt").read_text(encoding="utf-8"),
                "Example=100\n",
            )
            # Existing built-in Markdown is already current; only the new custom
            # target requires a physical write.
            self.assertEqual(result["written"], 1)


class P5OrphanMaterializationTests(unittest.TestCase):
    def test_removed_materialization_target_is_preserved_and_reported_as_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, _, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            old_path = project / "docs/catalog/product.md"
            old_bytes = old_path.read_bytes()
            descriptor = project / "docs/_structured/catalog/product.json"
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
            payload["$docengine"]["materialize"] = []
            descriptor.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            _, _, _, _, _, sync2 = p5_runtime(project)
            result = sync2.sync()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "attention_required")
            self.assertEqual(old_path.read_bytes(), old_bytes)
            self.assertEqual(
                [x["path"] for x in result["orphaned_materializations"]],
                ["catalog/product.md"],
            )


class P5ProtocolAndStateIntegrityTests(unittest.TestCase):
    def test_invalid_renderer_registration_stays_in_json_error_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                init.read_text(encoding="utf-8")
                + "\n\ndef register_renderers(registry):\n"
                  "    registry.register('markdown', lambda value, context: 'x')\n",
                encoding="utf-8",
            )
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["check", "--project-root", str(project), "--json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["materialize", "--all", "--project-root", str(project), "--json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["errors"])

    def test_materialization_state_rejects_noncanonical_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, _ = p5_runtime(project)
            materialization.materialize("resource://catalog/product")
            state_path = project / "docs/_dependency/state/materialization_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            record = next(iter(state["outputs"].values()))
            state["outputs"]["../escape.md"] = record
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(MaterializationError, "canonical materialization state path"):
                materialization.state.load()




class P5PostAxisRegressionTests(unittest.TestCase):
    def test_direct_materialize_refuses_changed_derived_target_without_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            # Establish a valid deterministic receipt and materialization state.
            _, _, _, _, materialization, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            path = project / "docs/catalog/price_with_tax.md"
            before = path.read_bytes()

            source = project / "docs/_structured/catalog/product.json"
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["data"]["price"] = 125
            source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            _, _, _, dependency2, materialization2, _ = p5_runtime(project)
            with self.assertRaisesRegex(MaterializationError, "rebuild|changed target|valid dependency state"):
                materialization2.materialize("resource://catalog/price_with_tax")
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(dependency2.diff("resource://catalog/price_with_tax")["changed"])

    def test_sync_failure_does_not_materialize_audit_incomplete_derived_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            builder = project / "docengine_project/builders.py"
            builder.write_text(
                'def build_price_with_tax(ctx):\n'
                '    price = ctx.untracked_read("resource://catalog/product#/price", reason="legacy")\n'
                '    tax_rate = ctx.read("resource://catalog/tax_policy#/rate")\n'
                '    return {"price": price, "tax_rate": tax_rate, "total": price * (1 + tax_rate)}\n\n'
                'def register(registry):\n'
                '    registry.register("resource://catalog/price_with_tax", build_price_with_tax, '
                'builder_id="catalog.price_with_tax", dependency_type="compute", comparator="exact")\n',
                encoding="utf-8",
            )
            path = project / "docs/catalog/price_with_tax.md"
            path.unlink(missing_ok=True)
            _, _, _, _, _, sync = p5_runtime(project)
            result = sync.sync()
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "sync_failed")
            self.assertIn("resource://catalog/price_with_tax", result["invalid_targets"])
            self.assertEqual(result["materialization"]["written"], 0)
            self.assertFalse(path.exists())

    def test_orphan_can_be_acknowledged_without_deleting_plain_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, _, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            old_path = project / "docs/catalog/product.md"
            descriptor = project / "docs/_structured/catalog/product.json"
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
            payload["$docengine"]["materialize"] = []
            descriptor.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            old_path.write_text("# Adopted plain documentation\n", encoding="utf-8")

            _, _, _, _, materialization2, sync2 = p5_runtime(project)
            first = sync2.sync()
            self.assertEqual(first["status"], "attention_required")
            state_before = materialization2.state.load()["outputs"]["catalog/product.md"].copy()
            ack = materialization2.acknowledge_orphan("file://catalog/product.md")
            self.assertTrue(ack["state_changed"])
            self.assertTrue(ack["file_preserved"])
            self.assertEqual(old_path.read_text(encoding="utf-8"), "# Adopted plain documentation\n")
            state_after = materialization2.state.load()["outputs"]["catalog/product.md"]
            self.assertTrue(state_after["orphan_acknowledged"])
            for key in ("owner_ref", "renderer", "renderer_revision", "input_revision", "output_digest", "resource_kind"):
                self.assertEqual(state_after[key], state_before[key])

            _, _, _, _, _, sync3 = p5_runtime(project)
            second = sync3.sync()
            self.assertEqual(second["status"], "ok")
            self.assertNotIn("catalog/product.md", [x["path"] for x in second["orphaned_materializations"]])
            self.assertIn("catalog/product.md", [x["path"] for x in second["acknowledged_orphaned_materializations"]])

    def test_orphan_ack_cli_is_machine_readable_and_preserves_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, _, sync = p5_runtime(project)
            sync.sync(all_targets=True)
            descriptor = project / "docs/_structured/catalog/product.json"
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
            payload["$docengine"]["materialize"] = []
            descriptor.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            path = project / "docs/catalog/product.md"
            before = path.read_bytes()
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main([
                    "materialize", "file://catalog/product.md", "--ack-orphan",
                    "--project-root", str(project), "--json",
                ])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "orphan_acknowledged")
            self.assertEqual(path.read_bytes(), before)

    def test_materialization_state_rejects_invalid_resource_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            _, _, _, _, materialization, _ = p5_runtime(project)
            materialization.materialize("resource://catalog/product")
            state_path = project / "docs/_dependency/state/materialization_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            record = next(iter(state["outputs"].values()))
            record["resource_kind"] = "evil"
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(MaterializationError, "resource_kind"):
                materialization.state.load()

    @pytest.mark.requires_symlink
    def test_materialization_state_rejects_symlinked_state_directory_inside_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            dep = project / "docs/_dependency"
            dep.mkdir(parents=True, exist_ok=True)
            state_dir = dep / "state"
            redirected = project / "docs/redirected_state"
            redirected.mkdir()
            shutil.rmtree(state_dir, ignore_errors=True)
            state_dir.symlink_to(redirected, target_is_directory=True)
            roots = discover_roots(project_root=project)
            with self.assertRaisesRegex(MaterializationError, "symlink"):
                MaterializationStateStore(roots)

    def test_builder_registration_error_stays_in_json_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fresh_copy(PRODUCT, tmp)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                init.read_text(encoding="utf-8")
                + "\n\ndef register_builders(registry):\n"
                  "    registry.register('resource://catalog/price_with_tax', lambda ctx: {'x': 1})\n"
                  "    registry.register('resource://catalog/price_with_tax', lambda ctx: {'x': 2})\n",
                encoding="utf-8",
            )
            for argv in (["check"], ["materialize", "--all"], ["sync"]):
                with self.subTest(argv=argv):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        code = main([*argv, "--project-root", str(project), "--json"])
                    payload = json.loads(stream.getvalue())
                    self.assertEqual(code, 3)
                    self.assertIn("ok", payload)
                    self.assertFalse(payload["ok"])
                    self.assertNotIn("Traceback", stream.getvalue())

    def test_broken_renderer_does_not_block_dependency_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                init.read_text(encoding="utf-8")
                + "\n\ndef register_renderers(registry):\n"
                  "    registry.register('markdown', lambda value, context: 'x')\n",
                encoding="utf-8",
            )
            for argv in (["check"], ["diff", "resource://catalog/price_with_tax"], ["explain", "resource://catalog/price_with_tax"]):
                with self.subTest(argv=argv):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        code = main([*argv, "--project-root", str(project), "--json"])
                    payload = json.loads(stream.getvalue())
                    self.assertEqual(code, 2)
                    self.assertTrue(payload["ok"])
                    self.assertTrue(payload["attention_required"])
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["materialize", "--all", "--project-root", str(project), "--json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])

if __name__ == "__main__":
    unittest.main()
