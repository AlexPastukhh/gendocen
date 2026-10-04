import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docengine.cli import main
from docengine.dependencies import DependencyRuntime
from docengine.extensions import ProjectExtensionError, load_project_extension
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog
from docengine.semantic import SemanticReviewRuntime, SemanticRuleError, SemanticValidationError

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample_project"
TARGET = "file://architecture/rationale.md"
SOURCE = "resource://policies/method_policy#/allowed_methods"


def services(project: Path):
    roots = discover_roots(project_root=project)
    catalog = ResourceCatalog.scan(roots)
    extension = load_project_extension(roots, catalog)
    runtime = DependencyRuntime(
        roots,
        catalog,
        extension.registry,
        semantic_rule_revisions=extension.semantic_registry.revisions_by_target(),
    )
    return roots, catalog, extension, runtime, SemanticReviewRuntime(runtime, extension.semantic_registry)


def mutate_methods(project: Path, methods):
    path = project / "docs/_structured/policies/method_policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["data"]["allowed_methods"] = list(methods)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class P4RegistryAndReviewPacketTests(unittest.TestCase):
    def test_sample_semantic_rule_is_loaded_and_graph_inspectable(self):
        _, _, extension, runtime, review = services(SAMPLE)
        rule = extension.semantic_registry.get(TARGET)
        self.assertEqual(rule.rule_id, "architecture.rationale-method-policy")
        self.assertEqual(rule.dependency_type, "semantic_review")
        self.assertEqual([(str(x.source), x.comparator) for x in rule.dependencies], [(SOURCE, "set")])
        graph = review.graph(TARGET)
        self.assertEqual(graph["rule_edges"][0]["source"], SOURCE)
        self.assertEqual(graph["rule_edges"][0]["target"], TARGET)

    def test_review_packet_validates_against_machine_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            _, _, _, _, review = services(project)
            packet = review.review_packet(TARGET)
            schema = json.loads((ROOT / "spec/schemas/REVIEW_PACKET.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(packet, schema)

    def test_initial_review_packet_contains_target_current_slices_and_no_semantic_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            _, _, _, _, review = services(project)
            packet = review.review_packet(TARGET)
            self.assertTrue(packet["review_context_id"].startswith("reviewctx-"))
            self.assertEqual(packet["computed_status"], "review_required")
            self.assertIsNone(packet["prior_receipt"])
            self.assertIsNone(packet["semantic_judgment"])
            self.assertIn("Architecture Rationale", packet["target_current"]["content"])
            self.assertEqual(packet["dependencies"][0]["source"], SOURCE)
            self.assertEqual(packet["dependencies"][0]["current"], ["method_a", "method_b"])
            self.assertIn("initial_validation_required", packet["reason_codes"])

    def test_check_surfaces_unvalidated_registered_rule_as_review_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            _, _, _, _, review = services(project)
            result = review.check_all()
            item = next(x for x in result["results"] if x["target"] == TARGET)
            self.assertEqual(item["status"], "review_required")
            self.assertTrue(item["registered_rule_unvalidated"])
            self.assertIn("initial_validation_required", item["diff"]["reason_codes"])
            self.assertFalse((project / "docs/_dependency/state/dependency_state.json").exists())

    def test_initial_validity_rule_uses_stale_consistently_in_explain_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                rules.read_text(encoding="utf-8").replace(
                    'dependency_type="semantic_review"',
                    'dependency_type="validity"',
                ),
                encoding="utf-8",
            )
            _, _, _, _, review = services(project)
            packet = review.review_packet(TARGET)
            self.assertEqual(packet["computed_status"], "stale")
            item = next(x for x in review.check_all()["results"] if x["target"] == TARGET)
            self.assertEqual(item["status"], "stale")
            self.assertTrue(item["registered_rule_unvalidated"])

    def test_legacy_validity_receipt_missing_rule_metadata_becomes_stale_not_review_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            legacy = DependencyRuntime(roots, catalog, extension.registry, semantic_rule_revisions={})
            legacy.record_explicit(TARGET, [(SOURCE, "set")], dependency_type="validity")

            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                rules.read_text(encoding="utf-8").replace(
                    'dependency_type="semantic_review"',
                    'dependency_type="validity"',
                ),
                encoding="utf-8",
            )
            _, _, _, _, review = services(project)
            item = next(x for x in review.check_all()["results"] if x["target"] == TARGET)
            self.assertEqual(item["status"], "stale")
            self.assertIn("semantic_rule_metadata_missing", item["diff"]["reason_codes"])

    def test_initial_compatibility_rule_remains_review_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                rules.read_text(encoding="utf-8").replace(
                    'dependency_type="semantic_review"',
                    'dependency_type="compatibility"',
                ),
                encoding="utf-8",
            )
            _, _, _, _, review = services(project)
            self.assertEqual(review.review_packet(TARGET)["computed_status"], "review_required")
            item = next(x for x in review.check_all()["results"] if x["target"] == TARGET)
            self.assertEqual(item["status"], "review_required")

    def test_semantic_rule_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                "def register_builders(registry):\n    registry.register('resource://architecture/system_summary', lambda ctx: {'title': 'ok'})\n"
                "def register_semantic_dependencies(registry):\n"
                "    registry.register('file://architecture/rationale.md', ['file://policies/plain.md'], rule_id='a')\n"
                "    registry.register('file://policies/plain.md', ['file://architecture/rationale.md'], rule_id='b')\n",
                encoding="utf-8",
            )
            (project / "docs/policies/plain.md").write_text("# Plain\n", encoding="utf-8")
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(SemanticRuleError, "cycle"):
                load_project_extension(roots, catalog)

    def test_semantic_rule_cannot_replace_same_exact_builder_target_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                "def register(registry):\n"
                "    registry.register('resource://architecture/system_summary', "
                "['resource://architecture/overview#/title'], rule_id='overlap')\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "also a deterministic builder target"):
                load_project_extension(roots, catalog)

    def test_semantic_rule_unknown_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                "def register_builders(registry):\n    registry.register('resource://architecture/system_summary', lambda ctx: {'title': 'ok'})\n"
                "def register_semantic_dependencies(registry):\n"
                "    registry.register('file://architecture/rationale.md', ['file://missing.md'], rule_id='bad')\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            runtime = DependencyRuntime(
                roots,
                catalog,
                extension.registry,
                semantic_rule_revisions=extension.semantic_registry.revisions_by_target(),
            )
            review = SemanticReviewRuntime(runtime, extension.semantic_registry)
            with self.assertRaisesRegex(Exception, "missing.md|unknown documentation file|plain canonical Markdown"):
                review.review_packet(TARGET)


class P4ValidationTests(unittest.TestCase):
    def _copy(self, tmp: str) -> Path:
        project = Path(tmp) / "project"
        shutil.copytree(SAMPLE, project)
        shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
        return project

    def _initial_validate(self, project: Path):
        _, _, _, runtime, review = services(project)
        packet = review.review_packet(TARGET)
        result = review.validate(
            TARGET,
            result="still-valid",
            reason="Initial semantic baseline reviewed.",
            review_context_id=packet["review_context_id"],
            evidence=("review-note:initial",),
            actor_kind="ai",
            actor_label="review-agent",
        )
        return runtime, result

    def test_initial_validation_records_actor_reason_evidence_and_official_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            before = (project / "docs/architecture/rationale.md").read_bytes()
            runtime, result = self._initial_validate(project)
            self.assertFalse(result["duplicate"])
            self.assertEqual(runtime.status()["targets"][TARGET]["status"], "valid")
            receipt = runtime.receipts.load(result["receipt_id"])
            self.assertEqual(receipt.semantic_rule_id, "architecture.rationale-method-policy")
            self.assertIsNotNone(receipt.target_revision)
            event = result["event"]
            self.assertEqual(event["event_type"], "semantic_validation")
            self.assertEqual(event["review"]["decision"], "still-valid")
            self.assertEqual(event["review"]["actor_kind"], "ai")
            self.assertEqual(event["review"]["actor_label"], "review-agent")
            self.assertEqual(event["review"]["reason"], "Initial semantic baseline reviewed.")
            self.assertEqual(event["review"]["evidence"], ["review-note:initial"])
            self.assertEqual((project / "docs/architecture/rationale.md").read_bytes(), before)
            self.assertTrue(runtime.verify_integrity()["ok"])

    def test_semantic_validation_event_validates_against_event_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            _, result = self._initial_validate(project)
            schema = json.loads((ROOT / "spec/schemas/DEPENDENCY_EVENT.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(result["event"], schema)

    def test_dependency_change_becomes_review_required_without_semantic_verdict_then_still_valid_advances_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            runtime, initial = self._initial_validate(project)
            old_receipt_id = initial["receipt_id"]
            before_target = (project / "docs/architecture/rationale.md").read_bytes()
            mutate_methods(project, ["method_a", "method_b", "method_c"])

            _, _, _, runtime2, review2 = services(project)
            checked = runtime2.check(TARGET)
            self.assertEqual(checked["status"], "review_required")
            packet = review2.review_packet(TARGET)
            self.assertIsNone(packet["semantic_judgment"])
            self.assertEqual(packet["dependencies"][0]["baseline"], ["method_a", "method_b"])
            self.assertEqual(packet["dependencies"][0]["current"], ["method_a", "method_b", "method_c"])
            self.assertTrue(packet["dependencies"][0]["diff"]["changed"])

            accepted = review2.validate(
                TARGET,
                result="still-valid",
                reason="Rationale remains valid when method_c is added.",
                review_context_id=packet["review_context_id"],
                actor_kind="human",
                actor_label="reviewer",
            )
            self.assertNotEqual(accepted["receipt_id"], old_receipt_id)
            self.assertEqual(runtime2.status()["targets"][TARGET]["status"], "valid")
            self.assertEqual((project / "docs/architecture/rationale.md").read_bytes(), before_target)
            history = runtime2.history(TARGET)
            self.assertIn(old_receipt_id, history["receipt_ids"])
            self.assertIn(accepted["receipt_id"], history["receipt_ids"])
            self.assertGreaterEqual(len(history["events"]), 3)  # initial validation, check, revalidation
            self.assertTrue(runtime2.verify_integrity()["ok"])

    def test_updated_requires_target_edit_and_still_valid_rejects_edited_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            mutate_methods(project, ["method_a", "method_b", "method_c"])
            target_path = project / "docs/architecture/rationale.md"
            target_path.write_text(target_path.read_text(encoding="utf-8") + "\nUpdated for method_c.\n", encoding="utf-8")
            _, _, _, runtime2, review2 = services(project)
            runtime2.check(TARGET)
            packet = review2.review_packet(TARGET)
            with self.assertRaisesRegex(SemanticValidationError, "still-valid cannot accept edited"):
                review2.validate(
                    TARGET,
                    result="still-valid",
                    reason="wrong decision",
                    review_context_id=packet["review_context_id"],
                )
            updated = review2.validate(
                TARGET,
                result="updated",
                reason="Target updated to cover method_c.",
                review_context_id=packet["review_context_id"],
                actor_kind="ai",
            )
            self.assertEqual(updated["decision"], "updated")
            self.assertEqual(runtime2.status()["targets"][TARGET]["status"], "valid")

    def test_updated_without_target_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime2, review2 = services(project)
            runtime2.check(TARGET)
            packet = review2.review_packet(TARGET)
            with self.assertRaisesRegex(SemanticValidationError, "updated requires the target"):
                review2.validate(
                    TARGET,
                    result="updated",
                    reason="No target edit happened.",
                    review_context_id=packet["review_context_id"],
                )

    def test_stale_review_context_is_rejected_without_advancing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime2, review2 = services(project)
            runtime2.check(TARGET)
            packet = review2.review_packet(TARGET)
            before_state = runtime2.state.load()
            mutate_methods(project, ["method_a", "method_b", "method_c", "method_d"])
            _, _, _, runtime3, review3 = services(project)
            with self.assertRaisesRegex(SemanticValidationError, "review context is stale"):
                review3.validate(
                    TARGET,
                    result="still-valid",
                    reason="Reviewed older dependency state.",
                    review_context_id=packet["review_context_id"],
                )
            after_state = runtime3.state.load()
            self.assertEqual(after_state["targets"][TARGET], before_state["targets"][TARGET])

    def test_exact_retry_is_idempotent_and_conflicting_reuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            _, _, _, runtime, review = services(project)
            packet = review.review_packet(TARGET)
            kwargs = dict(
                result="still-valid",
                reason="Reviewed once.",
                review_context_id=packet["review_context_id"],
                evidence=("e1",),
                actor_kind="ai",
                actor_label="agent",
            )
            first = review.validate(TARGET, **kwargs)
            revision_after_first = runtime.state.load()["state_revision"]
            events_after_first = len(runtime.events.all())
            second = review.validate(TARGET, **kwargs)
            self.assertTrue(second["duplicate"])
            self.assertEqual(second["receipt_id"], first["receipt_id"])
            self.assertEqual(runtime.state.load()["state_revision"], revision_after_first)
            self.assertEqual(len(runtime.events.all()), events_after_first)
            with self.assertRaisesRegex(SemanticValidationError, "already consumed"):
                review.validate(TARGET, **{**kwargs, "reason": "different reason"})

    def test_repeated_semantic_a_b_a_b_occurrences_are_new_transitions_not_old_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            _, initial = self._initial_validate(project)
            self.assertFalse(initial["duplicate"])

            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime_b1, review_b1 = services(project)
            runtime_b1.check(TARGET)
            packet_b1 = review_b1.review_packet(TARGET)
            accepted_b1 = review_b1.validate(
                TARGET,
                result="still-valid",
                reason="B occurrence",
                review_context_id=packet_b1["review_context_id"],
            )
            self.assertFalse(accepted_b1["duplicate"])

            mutate_methods(project, ["method_a", "method_b"])
            _, _, _, runtime_a1, review_a1 = services(project)
            runtime_a1.check(TARGET)
            packet_a1 = review_a1.review_packet(TARGET)
            accepted_a1 = review_a1.validate(
                TARGET,
                result="still-valid",
                reason="A occurrence",
                review_context_id=packet_a1["review_context_id"],
            )
            self.assertFalse(accepted_a1["duplicate"])

            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime_b2, review_b2 = services(project)
            runtime_b2.check(TARGET)
            packet_b2 = review_b2.review_packet(TARGET)
            self.assertNotEqual(packet_b2["review_context_id"], packet_b1["review_context_id"])
            before_revision = runtime_b2.state.load()["state_revision"]
            accepted_b2 = review_b2.validate(
                TARGET,
                result="still-valid",
                reason="B occurrence",
                review_context_id=packet_b2["review_context_id"],
            )
            self.assertFalse(accepted_b2["duplicate"])
            after = runtime_b2.state.load()
            self.assertGreater(after["state_revision"], before_revision)
            self.assertEqual(after["targets"][TARGET]["status"], "valid")
            self.assertEqual(after["targets"][TARGET]["last_receipt_id"], accepted_b2["receipt_id"])
            review_events = [
                event for event in runtime_b2.events.for_target(TARGET)
                if isinstance(event.get("review"), dict)
            ]
            self.assertEqual(len(review_events), 4)
            self.assertEqual(len({event["review"]["context_id"] for event in review_events}), 4)

    def test_consumed_old_context_after_later_target_transition_is_stale_not_duplicate_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime_b, review_b = services(project)
            runtime_b.check(TARGET)
            packet_b = review_b.review_packet(TARGET)
            review_b.validate(
                TARGET,
                result="still-valid",
                reason="B",
                review_context_id=packet_b["review_context_id"],
            )
            mutate_methods(project, ["method_a", "method_b"])
            _, _, _, runtime_a, review_a = services(project)
            runtime_a.check(TARGET)
            with self.assertRaisesRegex(SemanticValidationError, "stale"):
                review_a.validate(
                    TARGET,
                    result="still-valid",
                    reason="B",
                    review_context_id=packet_b["review_context_id"],
                )

    def test_reason_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            _, _, _, _, review = services(project)
            packet = review.review_packet(TARGET)
            with self.assertRaisesRegex(SemanticValidationError, "non-empty reason"):
                review.validate(
                    TARGET,
                    result="still-valid",
                    reason="  ",
                    review_context_id=packet["review_context_id"],
                )

    def test_direct_state_edit_cannot_pass_integrity_as_official_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            mutate_methods(project, ["method_a", "method_b", "method_c"])
            _, _, _, runtime2, _ = services(project)
            runtime2.check(TARGET)
            state_path = project / "docs/_dependency/state/dependency_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["targets"][TARGET]["status"] = "valid"
            state["targets"][TARGET]["changed_dependencies"] = []
            state["targets"][TARGET]["reason_codes"] = []
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            integrity = DependencyRuntime(discover_roots(project_root=project)).verify_integrity()
            self.assertFalse(integrity["ok"])
            self.assertTrue(any(x["code"] == "state_latest_event_mismatch" for x in integrity["issues"]))

    def test_semantic_rule_type_change_uses_current_type_without_spurious_old_status_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                rules.read_text(encoding="utf-8").replace(
                    'dependency_type="semantic_review"',
                    'dependency_type="validity"',
                ),
                encoding="utf-8",
            )
            _, _, _, runtime2, review2 = services(project)
            packet = review2.review_packet(TARGET)
            self.assertEqual(packet["computed_status"], "stale")
            before_events = list(runtime2.events.for_target(TARGET))
            checked = review2.check_all()
            item = next(x for x in checked["results"] if x["target"] == TARGET)
            self.assertEqual(item["status"], "stale")
            self.assertIn("semantic_rule_revision_changed", item["diff"]["reason_codes"])
            new_events = list(runtime2.events.for_target(TARGET))[len(before_events):]
            self.assertEqual(len(new_events), 1)
            self.assertEqual(new_events[0]["status"], "stale")
            self.assertNotEqual(new_events[0]["status"], "review_required")

    def test_semantic_rule_revision_change_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(rules.read_text(encoding="utf-8").replace('"set")', '"sequence")'), encoding="utf-8")
            _, _, ext2, runtime2, _ = services(project)
            checked = runtime2.check(TARGET)
            self.assertEqual(checked["status"], "review_required")
            self.assertIn("semantic_rule_revision_changed", checked["diff"]["reason_codes"])
            self.assertIn("rule://architecture.rationale-method-policy", checked["diff"]["changed_dependencies"])

    def test_rule_dependency_replacement_preserves_review_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy(tmp)
            self._initial_validate(project)
            rules = project / "docengine_project/dependency_rules/architecture/rationale.py"
            rules.write_text(
                rules.read_text(encoding="utf-8").replace(
                    '[("resource://policies/method_policy#/allowed_methods", "set")]',
                    '[("resource://architecture/overview#/title", "exact")]',
                ),
                encoding="utf-8",
            )
            _, _, _, runtime2, review2 = services(project)
            checked = runtime2.check(TARGET)
            self.assertEqual(checked["status"], "review_required")
            packet = review2.review_packet(TARGET)
            sources = {x["source"] for x in packet["dependencies"]}
            self.assertIn(SOURCE, sources)
            self.assertIn("resource://architecture/overview#/title", sources)
            accepted = review2.validate(
                TARGET,
                result="still-valid",
                reason="Rationale remains valid under the replacement semantic input.",
                review_context_id=packet["review_context_id"],
            )
            self.assertEqual(accepted["status"], "valid")
            self.assertTrue(runtime2.verify_integrity()["ok"])



class P4CliTests(unittest.TestCase):
    def test_explain_validate_history_json_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["explain", TARGET, "--project-root", str(project), "--json"])
            self.assertEqual(code, 2)
            packet = json.loads(stream.getvalue())
            context_id = packet["data"]["review_context_id"]
            self.assertIsNone(packet["data"]["semantic_judgment"])

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main([
                    "validate", TARGET,
                    "--result", "still-valid",
                    "--reason", "CLI initial review",
                    "--review-context", context_id,
                    "--actor-kind", "ai",
                    "--actor-label", "cli-agent",
                    "--evidence", "ticket:123",
                    "--project-root", str(project),
                    "--json",
                ])
            self.assertEqual(code, 0)
            validated = json.loads(stream.getvalue())
            self.assertTrue(validated["ok"])
            self.assertEqual(validated["data"]["decision"], "still-valid")

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["history", TARGET, "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            history = json.loads(stream.getvalue())
            self.assertTrue(any(e.get("review", {}).get("reason") == "CLI initial review" for e in history["data"]["events"]))

    def test_invalid_validate_result_returns_json_error_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main([
                    "validate", TARGET,
                    "--result", "not-a-decision",
                    "--reason", "bad",
                    "--review-context", "reviewctx-" + "0" * 64,
                    "--project-root", str(project),
                    "--json",
                ])
            self.assertEqual(code, 4)
            payload = json.loads(stream.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "usage_error")

    def test_invalid_actor_kind_returns_json_error_envelope_not_argparse_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main([
                    "validate", TARGET,
                    "--result", "still-valid",
                    "--reason", "bad actor",
                    "--review-context", "reviewctx-" + "0" * 64,
                    "--actor-kind", "robot",
                    "--project-root", str(project),
                    "--json",
                ])
            self.assertEqual(code, 4)
            payload = json.loads(stream.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "usage_error")
            self.assertIn("actor-kind", payload["errors"][0]["message"])

    def test_invalid_target_ref_returns_json_error_envelope_for_validate_and_explain(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            cases = [
                [
                    "validate", "file://../evil.md",
                    "--result", "still-valid",
                    "--reason", "bad ref",
                    "--review-context", "reviewctx-" + "0" * 64,
                    "--project-root", str(project),
                    "--json",
                ],
                [
                    "explain", "file://../evil.md",
                    "--project-root", str(project),
                    "--json",
                ],
            ]
            for argv in cases:
                with self.subTest(command=argv[0]):
                    stream = io.StringIO()
                    with contextlib.redirect_stdout(stream):
                        code = main(argv)
                    self.assertEqual(code, 4)
                    payload = json.loads(stream.getvalue())
                    self.assertFalse(payload["ok"])
                    self.assertIn(payload["meta"]["status"], {"usage_or_config_error", "usage_error"})
                    self.assertTrue(payload["errors"])

    def test_validate_without_required_semantic_inputs_returns_envelope_not_argparse_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["validate", TARGET, "--project-root", str(project), "--json"])
            self.assertEqual(code, 4)
            payload = json.loads(stream.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "usage_error")


if __name__ == "__main__":
    unittest.main()
