import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docengine.builders import BuildEngine
from docengine.cli import main
from docengine.dependencies import (
    ComparatorRegistry,
    DependencyRuntime,
    ExplicitDependency,
)
from docengine.extensions import load_project_extension
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "examples/product_tax_project"
SAMPLE = ROOT / "examples/sample_project"


def runtime_for(project: Path):
    roots = discover_roots(project_root=project)
    catalog = ResourceCatalog.scan(roots)
    extension = load_project_extension(roots, catalog)
    return roots, catalog, extension, DependencyRuntime(roots, catalog, extension.registry)


class P3BuildReceiptTests(unittest.TestCase):
    def _copy(self, source: Path, tmp: str) -> Path:
        project = Path(tmp) / "project"
        shutil.copytree(source, project)
        return project

    def test_field_baseline_contains_only_referenced_slice_and_ignores_unrelated_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            roots, catalog, extension, runtime = runtime_for(project)
            result = BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax")
            receipt = runtime.record_build(result)
            by_source = {d.source: d for d in receipt.dependencies}
            price_dep = by_source["resource://catalog/product#/price"]
            price_snapshot = runtime.baselines.load(price_dep.snapshot_ref, expected_hash=price_dep.baseline_hash)
            self.assertEqual(price_snapshot.value, 100)
            self.assertNotIsInstance(price_snapshot.value, dict)

            product = project / "docs/_structured/catalog/product.json"
            payload = json.loads(product.read_text(encoding="utf-8"))
            payload["data"]["description"] = "unrelated edit"
            product.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            _, _, extension2, runtime2 = runtime_for(project)
            check = runtime2.check("resource://catalog/price_with_tax")
            self.assertEqual(check["status"], "valid")
            self.assertFalse(check["diff"]["changed"])

    def test_referenced_field_change_marks_build_required_and_diff_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            _, catalog, extension, runtime = runtime_for(project)
            receipt = runtime.record_build(BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax"))
            product = project / "docs/_structured/catalog/product.json"
            payload = json.loads(product.read_text(encoding="utf-8"))
            payload["data"]["price"] = 125
            product.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            _, _, _, runtime2 = runtime_for(project)
            first_diff = runtime2.diff(receipt.target)
            second_diff = runtime2.diff(receipt.target)
            self.assertEqual(first_diff, second_diff)
            self.assertEqual(first_diff["changed_dependencies"], ["resource://catalog/product#/price"])
            price = next(d for d in first_diff["dependencies"] if d["source"].endswith("#/price"))
            self.assertEqual(price["comparator"], "exact")
            self.assertEqual(price["details"], {"old": 100, "new": 125})

            before_events = len(runtime2.events.all())
            first_check = runtime2.check(receipt.target)
            after_first = len(runtime2.events.all())
            second_check = runtime2.check(receipt.target)
            after_second = len(runtime2.events.all())
            self.assertEqual(first_check["status"], "build_required")
            self.assertTrue(first_check["state_changed"])
            self.assertFalse(second_check["state_changed"])
            self.assertGreater(after_first, before_events)
            self.assertEqual(after_first, after_second)

    def test_builder_revision_change_alone_marks_build_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            _, catalog, extension, runtime = runtime_for(project)
            receipt = runtime.record_build(BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax"))
            old_revision = receipt.builder_revision

            helper = project / "docengine_project/builders.py"
            helper.write_text(helper.read_text(encoding="utf-8") + "\n# revision-only edit\n", encoding="utf-8")
            _, _, extension2, runtime2 = runtime_for(project)
            self.assertNotEqual(extension2.source_revision, old_revision)
            diff = runtime2.diff(receipt.target)
            self.assertEqual(diff["changed_dependencies"], ["builder://catalog.price_with_tax"])
            builder_item = next(x for x in diff["dependencies"] if x.get("kind") == "builder_revision")
            self.assertEqual(builder_item["reason"], "builder_revision_changed")
            checked = runtime2.check(receipt.target)
            self.assertEqual(checked["status"], "build_required")


    def test_recording_same_build_twice_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            _, catalog, extension, runtime = runtime_for(project)
            result = BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax")
            first = runtime.record_build(result)
            events_after_first = len(runtime.events.all())
            second = runtime.record_build(result)
            events_after_second = len(runtime.events.all())
            self.assertEqual(first.receipt_id, second.receipt_id)
            self.assertEqual(events_after_first, events_after_second)

    def test_incomplete_provenance_is_not_marked_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            from docengine.builders import BuilderRegistry
            registry = BuilderRegistry(source_revision="test-rev")
            def build(ctx):
                price = ctx.untracked_read("resource://catalog/product#/price", reason="legacy direct access")
                return {"value": price}
            registry.register("resource://internal/incomplete", build)
            result = BuildEngine(catalog, registry).build("resource://internal/incomplete")
            runtime = DependencyRuntime(roots, catalog, registry)
            receipt = runtime.record_build(result)
            self.assertFalse(receipt.audit_complete)
            state = runtime.status()["targets"][receipt.target]
            self.assertEqual(state["status"], "invalid")
            self.assertIn("audit_incomplete", state["reason_codes"])

    def test_reverse_graph_exactly_maps_recorded_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(PRODUCT, tmp)
            _, catalog, extension, runtime = runtime_for(project)
            runtime.record_build(BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax"))
            graph = runtime.graph()
            edges = {(x["source"], x["target"]) for x in graph["edges"]}
            self.assertEqual(edges, {
                ("resource://catalog/product#/price", "resource://catalog/price_with_tax"),
                ("resource://catalog/tax_policy#/rate", "resource://catalog/price_with_tax"),
            })


class P3MarkdownDependencyTests(unittest.TestCase):
    def test_whole_markdown_dependency_needs_no_json_and_becomes_review_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            plain_source = project / "docs/policies/plain_policy.md"
            plain_source.write_text("# Plain policy\n\nRule A.\n", encoding="utf-8")
            roots, catalog, extension, runtime = runtime_for(project)
            target = "file://architecture/rationale.md"
            source = "file://policies/plain_policy.md"
            receipt = runtime.record_explicit(
                target,
                [ExplicitDependency.create(source, comparator="text_unified")],
                dependency_type="semantic_review",
            )
            self.assertEqual(receipt.dependencies[0].granularity, "whole_file")
            self.assertFalse((project / "docs/_structured/architecture/rationale.json").exists())

            policy = project / "docs/policies/plain_policy.md"
            policy.write_text(policy.read_text(encoding="utf-8") + "\nNew semantic rule.\n", encoding="utf-8")
            _, _, _, runtime2 = runtime_for(project)
            diff = runtime2.diff(target)
            self.assertTrue(diff["changed"])
            item = diff["dependencies"][0]
            self.assertEqual(item["comparator"], "text_unified")
            self.assertIn("New semantic rule.", item["details"]["unified_diff"])
            check = runtime2.check(target)
            self.assertEqual(check["status"], "review_required")
            # Engine only reports structural invalidation; it does not mutate content.
            self.assertIn("architecture rationale", (project / "docs/architecture/rationale.md").read_text(encoding="utf-8").lower())

    def test_explicit_validation_tracks_target_revision_and_target_edit_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            source_path = project / "docs/policies/plain_policy.md"
            source_path.write_text("# Policy\n\nRule A.\n", encoding="utf-8")
            roots, catalog, extension, runtime = runtime_for(project)
            target = "file://architecture/rationale.md"
            receipt = runtime.record_explicit(
                target,
                [("file://policies/plain_policy.md", "text_unified")],
                dependency_type="semantic_review",
            )
            self.assertIsNotNone(receipt.target_revision)

            target_path = project / "docs/architecture/rationale.md"
            target_path.write_text(target_path.read_text(encoding="utf-8") + "\nClarification.\n", encoding="utf-8")
            _, _, _, runtime2 = runtime_for(project)
            diff = runtime2.diff(target)
            self.assertTrue(diff["changed"])
            self.assertEqual(diff["changed_dependencies"], [])
            self.assertIn("target_changed_since_validation", diff["reason_codes"])
            self.assertTrue(diff["target_revision"]["changed"])
            checked = runtime2.check(target)
            self.assertEqual(checked["status"], "review_required")

    def test_missing_explicit_validation_target_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            source_path = project / "docs/policies/plain_policy.md"
            source_path.write_text("# Policy\n", encoding="utf-8")
            _, _, _, runtime = runtime_for(project)
            target = "file://architecture/rationale.md"
            runtime.record_explicit(
                target,
                [("file://policies/plain_policy.md", "text_unified")],
                dependency_type="semantic_review",
            )
            (project / "docs/architecture/rationale.md").unlink()
            _, _, _, runtime2 = runtime_for(project)
            result = runtime2.check(target)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("target_unavailable", result["diff"]["reason_codes"])

    def test_line_ending_only_change_is_not_semantic_text_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            plain_source = project / "docs/policies/plain_policy.md"
            plain_source.write_text("# Plain policy\n\nRule A.\n", encoding="utf-8")
            _, _, _, runtime = runtime_for(project)
            target = "file://architecture/rationale.md"
            source = "file://policies/plain_policy.md"
            runtime.record_explicit(target, [(source, "text_unified")], dependency_type="validity")
            path = project / "docs/policies/plain_policy.md"
            text = path.read_text(encoding="utf-8")
            path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
            _, _, _, runtime2 = runtime_for(project)
            diff = runtime2.diff(target)
            self.assertFalse(diff["changed"])
            self.assertEqual(runtime2.check(target)["status"], "valid")


class P3ReadOnlyAndFailureSemanticsTests(unittest.TestCase):
    def test_dependency_runtime_refuses_symlinked_baseline_store(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            dep = project / "docs/_dependency"
            shutil.rmtree(dep / "baselines")
            outside = Path(outside_tmp) / "baselines"
            outside.mkdir()
            (dep / "baselines").symlink_to(outside, target_is_directory=True)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            with self.assertRaisesRegex(Exception, "symlink|escapes"):
                DependencyRuntime(roots, catalog, extension.registry)
            self.assertEqual(list(outside.iterdir()), [])

    def test_read_only_status_and_graph_do_not_create_dependency_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "docs").mkdir()
            (project / "docs/readme.md").write_text("# docs\n", encoding="utf-8")
            dep = project / "docs/_dependency"
            self.assertFalse(dep.exists())
            for command in ("status", "graph"):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = main([command, "--project-root", str(project), "--json"])
                self.assertEqual(code, 0)
                self.assertFalse(dep.exists(), command)


    def test_check_with_broken_builder_reports_invalid_instead_of_hiding_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            (project / "docengine_project/__init__.py").write_text("this is not valid python !!!\n", encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["check", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            payload = json.loads(stream.getvalue())
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["attention_required"])
            self.assertTrue(payload["data"]["runtime_diagnostics"])
            result = payload["data"]["results"][0]
            self.assertEqual(result["status"], "invalid")
            self.assertIn("builder_unavailable", result["diff"]["reason_codes"])

    def test_status_history_graph_remain_available_when_builder_package_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            # Existing example already carries a valid P3 receipt/state/history. Break code afterwards.
            (project / "docengine_project/__init__.py").write_text("this is not valid python !!!\n", encoding="utf-8")
            target = "resource://catalog/price_with_tax"
            for argv in (["status"], ["history", target], ["graph", target]):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    code = main([*argv, "--project-root", str(project), "--json"])
                self.assertEqual(code, 0, (argv, stream.getvalue()))
                payload = json.loads(stream.getvalue())
                self.assertTrue(payload["ok"])

    def test_duplicate_explicit_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            source_path = project / "docs/policies/plain_policy.md"
            source_path.write_text("# Policy\n", encoding="utf-8")
            _, _, _, runtime = runtime_for(project)
            with self.assertRaisesRegex(Exception, "duplicate dependency sources"):
                runtime.record_explicit(
                    "file://architecture/rationale.md",
                    [
                        ("file://policies/plain_policy.md", "text_unified"),
                        ("file://policies/plain_policy.md", "text_unified"),
                    ],
                    dependency_type="semantic_review",
                )

    def test_missing_dependency_source_marks_target_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            source_path = project / "docs/policies/plain_policy.md"
            source_path.write_text("# Policy\n", encoding="utf-8")
            _, _, _, runtime = runtime_for(project)
            target = "file://architecture/rationale.md"
            runtime.record_explicit(target, [("file://policies/plain_policy.md", "text_unified")], dependency_type="semantic_review")
            source_path.unlink()
            _, _, _, runtime2 = runtime_for(project)
            result = runtime2.check(target)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("source_unavailable", result["diff"]["reason_codes"])


class P3ComparatorTests(unittest.TestCase):
    def test_required_comparators_are_present_and_deterministic(self):
        registry = ComparatorRegistry()
        self.assertEqual(set(registry.ids), {"exact", "json_structured", "sequence", "set", "text_unified"})
        cases = [
            ("exact", 1, 2),
            ("json_structured", {"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}),
            ("sequence", [1, 2, 3], [1, 4, 3]),
            ("set", ["a", "b"], ["b", "c"]),
            ("text_unified", "a\nb\n", "a\nc\n"),
        ]
        for comparator, old, new in cases:
            with self.subTest(comparator=comparator):
                first = registry.compare(comparator, old, new).to_dict()
                second = registry.compare(comparator, old, new).to_dict()
                self.assertTrue(first["changed"])
                self.assertEqual(first, second)


class P3IntegrityTests(unittest.TestCase):
    def test_missing_or_corrupt_baseline_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            _, catalog, extension, runtime = runtime_for(project)
            receipt = runtime.record_build(BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax"))
            dep = receipt.dependencies[0]
            digest = dep.snapshot_ref.rsplit("/", 1)[1]
            path = project / "docs/_dependency/baselines" / f"sha256-{digest}.json"
            path.write_text('{"corrupt":true}\n', encoding="utf-8")
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "dependency_evidence_invalid" for i in integrity["issues"]))


    def test_event_pointing_to_missing_receipt_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            roots = discover_roots(project_root=project)
            runtime = DependencyRuntime(roots)
            event_path = project / "docs/_dependency/events/dependency_events.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            stable = {
                "event_type": event["event_type"],
                "target": event["target"],
                "receipt_id": "receipt-" + "0" * 64,
                "status": event["status"],
                "changed_dependencies": event["changed_dependencies"],
                "reason_codes": event["reason_codes"],
            }
            import hashlib
            raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            event.update(stable)
            event["event_id"] = "event-" + hashlib.sha256(raw).hexdigest()
            event_path.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "event_receipt_missing" for i in integrity["issues"]))

    def test_state_changed_dependency_must_be_explainable_by_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            state_path = project / "docs/_dependency/state/dependency_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            target = next(iter(state["targets"]))
            state["targets"][target]["changed_dependencies"] = ["resource://bogus/item#/value"]
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            runtime = DependencyRuntime(discover_roots(project_root=project))
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "state_changed_dependency_unknown" for i in integrity["issues"]))

    def test_event_changed_dependency_must_be_explainable_by_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            event_path = project / "docs/_dependency/events/dependency_events.jsonl"
            event = json.loads(event_path.read_text(encoding="utf-8").splitlines()[0])
            event["changed_dependencies"] = ["resource://bogus/item#/value"]
            stable = {
                "event_type": event["event_type"],
                "target": event["target"],
                "receipt_id": event["receipt_id"],
                "status": event["status"],
                "changed_dependencies": event["changed_dependencies"],
                "reason_codes": event["reason_codes"],
            }
            import hashlib
            raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            event["event_id"] = "event-" + hashlib.sha256(raw).hexdigest()
            event_path.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            runtime = DependencyRuntime(discover_roots(project_root=project))
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "event_changed_dependency_unknown" for i in integrity["issues"]))

    def test_receipt_audit_complete_must_be_boolean_even_if_old_hash_would_otherwise_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            receipt_path = next((project / "docs/_dependency/receipts").glob("receipt-*.json"))
            data = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertIs(data["audit_complete"], True)
            data["audit_complete"] = "false"
            receipt_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            runtime = DependencyRuntime(discover_roots(project_root=project))
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "receipt_store_invalid" for i in integrity["issues"]))

    def test_receipt_timestamp_tampering_is_detected_by_receipt_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            receipt_path = next((project / "docs/_dependency/receipts").glob("receipt-*.json"))
            data = json.loads(receipt_path.read_text(encoding="utf-8"))
            data["validated_at"] = "2025-01-01T00:00:00Z"
            receipt_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            roots = discover_roots(project_root=project)
            runtime = DependencyRuntime(roots)
            integrity = runtime.verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(i["code"] == "receipt_store_invalid" for i in integrity["issues"]))

    def test_receipt_state_and_events_are_explainable(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            _, catalog, extension, runtime = runtime_for(project)
            receipt = runtime.record_build(BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax"))
            status = runtime.status()
            entry = status["targets"][receipt.target]
            self.assertEqual(entry["last_receipt_id"], receipt.receipt_id)
            history = runtime.history(receipt.target)
            self.assertIn(receipt.receipt_id, history["receipt_ids"])
            self.assertTrue(any(event["receipt_id"] == receipt.receipt_id for event in history["events"]))
            explanation = runtime.explain(receipt.target)
            self.assertEqual(explanation["receipt"]["receipt_id"], receipt.receipt_id)
            self.assertTrue(runtime.verify_integrity()["ok"])


class P3CliTests(unittest.TestCase):
    def test_status_check_diff_explain_history_graph_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            _, catalog, extension, runtime = runtime_for(project)
            target = "resource://catalog/price_with_tax"
            runtime.record_build(BuildEngine(catalog, extension.registry).build(target))

            for argv in [
                ["status"], ["check"], ["diff", target], ["explain", target], ["history", target], ["graph", target]
            ]:
                with self.subTest(argv=argv):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        code = main([*argv, "--project-root", str(project), "--json"])
                    self.assertEqual(code, 0)
                    payload = json.loads(stream.getvalue())
                    self.assertTrue(payload["ok"])
                    self.assertEqual(payload["command"], argv[0])
                    self.assertIn("roots", payload["data"])


if __name__ == "__main__":
    unittest.main()

class P3ReceiptReactivationTests(unittest.TestCase):
    def test_reactivating_content_stable_receipt_is_current_and_has_new_event_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            source_a = project / "docs/policies/source_a.md"
            source_b = project / "docs/policies/source_b.md"
            source_a.write_text("# A\n", encoding="utf-8")
            source_b.write_text("# B\n", encoding="utf-8")
            target = "file://architecture/rationale.md"

            _, _, _, runtime = runtime_for(project)
            receipt_a1 = runtime.record_explicit(
                target,
                [("file://policies/source_a.md", "text_unified")],
                dependency_type="semantic_review",
            )
            receipt_b = runtime.record_explicit(
                target,
                [("file://policies/source_b.md", "text_unified")],
                dependency_type="semantic_review",
            )
            receipt_a2 = runtime.record_explicit(
                target,
                [("file://policies/source_a.md", "text_unified")],
                dependency_type="semantic_review",
            )

            self.assertEqual(receipt_a1.receipt_id, receipt_a2.receipt_id)
            self.assertNotEqual(receipt_a1.receipt_id, receipt_b.receipt_id)

            state = runtime.state.load()
            self.assertEqual(state["targets"][target]["last_receipt_id"], receipt_a1.receipt_id)
            self.assertEqual(state["state_revision"], 3)

            events = runtime.events.for_target(target)
            self.assertEqual(len(events), 3)
            self.assertEqual([event["state_revision"] for event in events], [1, 2, 3])
            self.assertEqual(events[-1]["receipt_id"], receipt_a1.receipt_id)

            graph = runtime.graph(target)
            self.assertEqual(graph["upstream"], ["file://policies/source_a.md"])
            self.assertTrue(runtime.verify_integrity()["ok"])

class P3StateRevisionCompatibilityTests(unittest.TestCase):
    def test_legacy_state_and_events_without_state_revision_remain_readable_and_upgrade_on_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)

            # The bundled product fixture is kept current for release/verify coverage.
            # Construct the legacy P3 representation explicitly so this compatibility
            # test does not rely on a permanently stale example fixture.
            events_path = project / "docs/_dependency/events/dependency_events.jsonl"
            existing_events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            legacy_event = next(event for event in existing_events if event.get("state_revision") is None)
            events_path.write_text(
                json.dumps(legacy_event, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            state_path = project / "docs/_dependency/state/dependency_state.json"
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            state_payload.pop("state_revision", None)
            target_state = state_payload["targets"]["resource://catalog/price_with_tax"]
            target_state["last_receipt_id"] = legacy_event["receipt_id"]
            target_state["status"] = "valid"
            target_state["changed_dependencies"] = []
            target_state["reason_codes"] = []
            state_path.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")

            _, _, _, runtime = runtime_for(project)

            legacy_state = runtime.state.load()
            self.assertEqual(legacy_state["state_revision"], 0)
            legacy_events = runtime.events.all()
            self.assertTrue(legacy_events)
            self.assertTrue(all(event.get("state_revision") is None for event in legacy_events))
            self.assertTrue(runtime.verify_integrity()["ok"])

            product = project / "docs/_structured/catalog/product.json"
            payload = json.loads(product.read_text(encoding="utf-8"))
            payload["data"]["price"] = 125
            product.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            _, _, _, runtime2 = runtime_for(project)
            result = runtime2.check("resource://catalog/price_with_tax")
            self.assertEqual(result["status"], "build_required")
            upgraded = runtime2.state.load()
            self.assertEqual(upgraded["state_revision"], 1)
            new_events = runtime2.events.all()
            revised = [event for event in new_events if event.get("state_revision") is not None]
            self.assertEqual([event["state_revision"] for event in revised], [1])
            self.assertTrue(runtime2.verify_integrity()["ok"])
