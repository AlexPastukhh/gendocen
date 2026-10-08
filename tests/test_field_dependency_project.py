"""Field-granular project authoring through the existing whole-resource runtime."""

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from docengine.builders import BuildCycleError, BuildEngine, BuilderRegistry
from docengine.extensions import load_project_extension
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog
from tests.test_builders import MemoryStore
from tests.test_documentation_workflows import run_json, _rootless_zero_context_project_commands

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/field_dependency_project"
spec = importlib.util.spec_from_file_location(
    "_gendocen_test_field_helper", FIXTURE / "docengine_project/fields.py"
)
helper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helper
spec.loader.exec_module(helper)
FieldPlan = helper.FieldPlan
FieldPlanError = helper.FieldPlanError


class FieldDependencyProjectTests(unittest.TestCase):
    def test_cold_transitive_input_and_producer_failures_recover(self):
        for failure in ["missing", "producer"]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(FIXTURE, project)
                path = project / ("docs/_structured/inputs/C.json" if failure == "missing" else "docengine_project/builders/fields/B_a1.py")
                original = path.read_bytes()
                if failure == "missing":
                    value = json.loads(original)
                    del value["data"]["x"]
                    path.write_text(json.dumps(value) + "\n")
                else:
                    path.write_text('def produce(ctx, fields):\n    raise ValueError("cold producer failure")\n')
                code, result = run_json(["sync", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3, result)
                self.assertFalse((project / "docs/views/A.md").exists())
                path.write_bytes(original)
                for name in ["sync", "verify"]:
                    code, result = run_json([name, "--project-root", str(project), "--json"])
                    self.assertEqual(code, 0, result)

    def test_demand_reads_do_not_build_unrelated_fields_and_share_session_cache(self):
        calls = []
        fields = FieldPlan()
        fields.input("C", "x", "resource://inputs/C#/x")

        def a1(ctx, plan):
            calls.append("B.a1")
            return plan.read(ctx, "C", "x") * 2

        def g(ctx, plan):
            calls.append("A.g")
            return plan.read(ctx, "B", "a1")

        def g1(ctx, plan):
            calls.append("B.g1")
            return plan.read(ctx, "A", "g") + 1

        fields.computed("B", "a1", "resource://fields/B_a1", a1)
        fields.computed("A", "g", "resource://fields/A_g", g)
        fields.computed("B", "g1", "resource://fields/B_g1", g1)
        registry = BuilderRegistry()
        fields.register(registry)
        store = MemoryStore({"inputs.C": {"x": 10}})
        engine = BuildEngine(store, registry)
        self.assertEqual(engine.build("resource://fields/A_g").to_builtin(), {"value": 20})
        self.assertEqual(calls, ["A.g", "B.a1"])
        calls.clear()

        def combined(ctx):
            return {"g": fields.read(ctx, "A", "g"), "g1": fields.read(ctx, "B", "g1")}

        registry.register("resource://views/combined", combined)
        self.assertEqual(engine.build("resource://views/combined").to_builtin(), {"g": 20, "g1": 21})
        self.assertEqual(calls, ["A.g", "B.a1", "B.g1"])
        self.assertEqual(store.objects["inputs.C"].to_builtin(), {"x": 10})

    def test_missing_required_input_and_unknown_provider_do_not_guess_a_builder(self):
        fields = FieldPlan()
        fields.input("A", "a", "resource://inputs/A#/a")
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A", "resource://inputs/A"))
        engine = BuildEngine(MemoryStore({"inputs.A": {}}), registry)
        with self.assertRaisesRegex(FieldPlanError, r"required input A.a is missing: resource://inputs/A#/a"):
            engine.build("resource://views/A")
        registry.register("resource://views/unknown", lambda ctx: {"x": fields.read(ctx, "A", "unknown")})
        with self.assertRaisesRegex(FieldPlanError, "no declared provider for A.unknown"):
            engine.build("resource://views/unknown")

    def test_true_field_cycle_is_reported_as_internal_resource_path(self):
        fields = FieldPlan()
        fields.computed("A", "g", "resource://fields/A_g", lambda ctx, plan: plan.read(ctx, "B", "g1"))
        fields.computed("B", "g1", "resource://fields/B_g1", lambda ctx, plan: plan.read(ctx, "A", "g"))
        registry = BuilderRegistry()
        fields.register(registry)
        with self.assertRaises(BuildCycleError) as caught:
            BuildEngine(MemoryStore({}), registry).build("resource://fields/A_g")
        self.assertEqual(caught.exception.cycle, (
            "resource://fields/A_g", "resource://fields/B_g1", "resource://fields/A_g"
        ))

    def test_raw_override_tracks_presence_and_preserves_null(self):
        fields = FieldPlan()
        fields.computed("B", "a/1~", "resource://fields/B_a1", lambda ctx, plan: 20,
                        raw_override="resource://inputs/B#/a~11~0")
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/B", lambda ctx: fields.compose(ctx, "B", "resource://inputs/B"))
        store = MemoryStore({"inputs.B": {"a/1~": None}})
        engine = BuildEngine(store, registry)
        self.assertEqual(engine.build("resource://views/B").to_builtin(), {"a/1~": None})
        result = engine.build("resource://fields/B_a1")
        self.assertEqual([str(d.ref) for d in result.provenance.dependencies], ["resource://inputs/B"])
        self.assertEqual(store.objects["inputs.B"].to_builtin(), {"a/1~": None})

    def test_raw_value_cannot_silently_override_a_computed_field(self):
        fields = FieldPlan()
        fields.computed("A", "g", "resource://fields/A_g", lambda ctx, plan: 20)
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A", "resource://inputs/A"))
        with self.assertRaisesRegex(FieldPlanError, "raw field conflicts with computed A.g"):
            BuildEngine(MemoryStore({"inputs.A": {"g": 99}}), registry).build("resource://views/A")

    def test_provider_ownership_and_registration_are_explicit(self):
        fields = FieldPlan()
        fields.input("A", "a", "resource://inputs/A#/a")
        with self.assertRaisesRegex(FieldPlanError, "duplicate provider"):
            fields.computed("A", "a", "resource://fields/A_a", lambda ctx, plan: 1)
        fields.computed("A", "g", "resource://fields/A_g", lambda ctx, plan: 20)
        with self.assertRaisesRegex(FieldPlanError, "distinct targets"):
            fields.computed("B", "g1", "resource://fields/A_g", lambda ctx, plan: 21)
        with self.assertRaisesRegex(FieldPlanError, "top-level raw field"):
            fields.computed("B", "a1", "resource://fields/B_a1", lambda ctx, plan: 20,
                            raw_override="resource://inputs/B#/nested/a1")
        fields.register(BuilderRegistry())
        with self.assertRaisesRegex(FieldPlanError, "before registering"):
            fields.input("B", "b1", "resource://inputs/B#/b1")

    def test_cli_lifecycle_and_source_switching(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURE, project)

            def command(name, *args):
                code, result = run_json([name, *args, "--project-root", str(project), "--json"])
                self.assertEqual(code, 0, result)
                return result

            def mutate(name, changes=None, remove=()):
                path = project / f"docs/_structured/inputs/{name}.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                data["data"].update(changes or {})
                for key in remove:
                    del data["data"][key]
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

            def assert_values(g, g1):
                a = (project / "docs/views/A.md").read_text(encoding="utf-8")
                b = (project / "docs/views/B.md").read_text(encoding="utf-8")
                self.assertIn(f"**G:** {g}\n", a)
                self.assertIn(f"**A1:** {g}\n", b)
                self.assertIn(f"**G1:** {g1}\n", b)

            command("sync")
            assert_values(20, 21)
            command("verify")
            graph = command("graph")
            self.assertIn("resource://fields/B_a1#/value", json.dumps(graph))
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            self.assertEqual(len(extension.registry.specs), 5)
            self.assertNotIn("fields.B_a1", {r.resource_id for r in catalog.managed})

            mutate("C", {"x": 12})
            command("sync")
            assert_values(24, 25)
            mutate("C", {"unused_note": "changed"})
            self.assertEqual(command("sync")["data"]["rebuilt"], [])
            mutate("B", {"a1": 99})
            command("sync")
            assert_values(99, 100)
            mutate("C", {"x": 13})
            self.assertEqual(command("sync")["data"]["rebuilt"], [])
            assert_values(99, 100)
            mutate("B", remove=("a1",))
            command("sync")
            assert_values(26, 27)
            command("verify")
            before = (project / "docs/views/A.md").read_bytes()
            mutate("A", remove=("a",))
            code, missing = run_json([
                "rebuild", "resource://views/A", "--project-root", str(project), "--json"
            ])
            self.assertEqual(code, 3, missing)
            self.assertIn("required input A.a is missing: resource://inputs/A#/a", json.dumps(missing))
            self.assertNotIn("dependency cycle", json.dumps(missing))
            self.assertEqual((project / "docs/views/A.md").read_bytes(), before)

    def test_clean_chat_route_and_copyable_commands(self):
        for relative in ("docs/CLEAN_CHAT_QUICKSTART.md", "docs/CORE_WORKFLOWS.md",
                         "docs/CODE_MODEL.md", "docs/AI_USAGE_PROTOCOL.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("FIELD_DEPENDENCIES.md", text)
        for relative in ("docs/FIELD_DEPENDENCIES.md", "examples/field_dependency_project/README.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(_rootless_zero_context_project_commands(text), [], relative)

    def test_transitive_source_failures_classify_invalid_and_recover(self):
        for failure in ("missing", "producer"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(FIXTURE, project)

                def command(name):
                    return run_json([name, "--project-root", str(project), "--json"])

                self.assertEqual(command("sync")[0], 0)
                output = project / "docs/views/A.md"
                before = output.read_bytes()
                path = (project / "docs/_structured/inputs/C.json" if failure == "missing"
                        else project / "docengine_project/builders/fields/B_a1.py")
                original = path.read_bytes()
                if failure == "missing":
                    value = json.loads(original)
                    del value["data"]["x"]
                    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
                else:
                    path.write_text('def produce(ctx, fields):\n    raise ValueError("broken producer")\n', encoding="utf-8")
                for name in ("check", "sync", "verify"):
                    code, result = command(name)
                    self.assertEqual(code, 3, result)
                    self.assertNotIn('"internal_error"', json.dumps(result))
                code, result = command("status")
                self.assertEqual(code, 3, result)
                self.assertEqual(result["data"]["targets"]["resource://views/A"]["status"], "invalid")
                self.assertEqual(output.read_bytes(), before)
                path.write_bytes(original)
                for name in ("sync", "verify"):
                    code, result = command(name)
                    self.assertEqual(code, 0, result)


if __name__ == "__main__":
    unittest.main()
