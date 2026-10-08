"""Nested ownership, demand composition and executable project regressions."""
import collections
import graphlib
import json
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from docengine.builders import BuildCycleError, BuildEngine, BuilderRegistry
from tests.test_builders import MemoryStore
from tests.test_documentation_workflows import run_json
from tests.test_field_dependency_project import FieldPlan, FieldPlanError, ROOT

FIXTURE = ROOT / "examples/nested_field_project"


class NestedFieldTests(unittest.TestCase):
    def test_equal_nested_override_updates_evidence_and_read_only_commands_preserve_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURE, project)

            def command(name, *args):
                code, result = run_json([name, *args, "--project-root", str(project), "--json"])
                self.assertEqual(code, 0, result)
                return result

            def state():
                return json.loads((project / "docs/_dependency/state/dependency_state.json").read_text())["targets"]

            def mutate(name, change):
                path = project / f"docs/_structured/inputs/{name}.json"
                value = json.loads(path.read_text())
                change(value["data"])
                path.write_text(json.dumps(value) + "\n")

            command("sync")
            target = "resource://fields/A_budget"
            old = state()[target]["last_receipt_id"]
            markdown = (project / "docs/views/A.md").read_bytes()
            mutate("A", lambda data: data["plan"].update(budget=50))
            command("sync")
            active = state()[target]["last_receipt_id"]
            self.assertNotEqual(old, active)
            receipt = json.loads((project / f"docs/_dependency/receipts/{active}.json").read_text())
            self.assertEqual([item["source"] for item in receipt["dependencies"]], ["resource://inputs/A"])
            self.assertEqual((project / "docs/views/A.md").read_bytes(), markdown)
            mutate("C", lambda data: data.update(rate=7))
            command("sync")
            self.assertEqual(state()[target]["last_receipt_id"], active)
            self.assertEqual((project / "docs/views/A.md").read_bytes(), markdown)
            mutate("A", lambda data: data["plan"].update(budget=99))
            command("sync")
            self.assertIn("**Budget:** 99", (project / "docs/views/A.md").read_text())
            mutate("A", lambda data: data["plan"].pop("budget"))
            command("sync")
            self.assertIn("**Budget:** 70", (project / "docs/views/A.md").read_text())
            self.assertEqual(command("sync")["data"]["rebuilt"], [])
            before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            for name, args in [("verify", ()), ("diff", ("resource://views/A",)),
                               ("explain", ("resource://views/A",)), ("status", ()),
                               ("history", ("resource://views/A",)), ("graph", ())]:
                command(name, *args)
            after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_array_shape_and_atomic_slice_changes_update_provenance(self):
        fields = FieldPlan()
        fields.document("A", "resource://inputs/A")
        fields.computed_path("A", "/items/0/value", "resource://fields/value",
                             lambda ctx, p: ctx.read("resource://inputs/B#/items/0/x"))
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A"))
        versions, values = [], []
        for raw_a, raw_b in [({"items": [{}]}, {"items": [{"x": 3}]}),
                             ({"items": [{}, {"keep": True}]}, {"items": [{"x": 3}]}),
                             ({"items": [{}, {"keep": True}]}, {"items": [{"x": 4}]})]:
            store = MemoryStore({"inputs.A": raw_a, "inputs.B": raw_b})
            result = BuildEngine(store, registry).build("resource://views/A")
            versions.append(result.provenance.provenance_digest)
            values.append(result.to_builtin())
            self.assertEqual(store.objects["inputs.A"].to_builtin(), raw_a)
        self.assertEqual(len(set(versions)), 3)
        self.assertEqual(values, [{"items": [{"value": 3}]},
                                  {"items": [{"value": 3}, {"keep": True}]},
                                  {"items": [{"value": 4}, {"keep": True}]}])

    def test_renamed_composite_keeps_old_target_via_explicit_compatibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURE, project)
            def command(name):
                return run_json([name, "--project-root", str(project), "--json"])
            self.assertEqual(command("sync")[0], 0)
            raw = project / "docs/_structured/inputs/A.json"
            value = json.loads(raw.read_text())
            value["data"]["execution"] = value["data"].pop("plan")
            raw.write_text(json.dumps(value) + "\n")
            for name in ["field_plan.py", "builders/fields/C_total.py"]:
                path = project / "docengine_project" / name
                path.write_text(path.read_text().replace('/plan/', '/execution/'))
            self.assertEqual(command("sync")[0], 3)  # old receipt still needs its registered target
            init = project / "docengine_project/__init__.py"
            with init.open("a") as f:
                f.write('\n    from .fields import FieldPlan\n    old = FieldPlan.object_target("A", "/plan")\n    new = FieldPlan.object_target("A", "/execution")\n    registry.register(old, lambda ctx: ctx.get(new).to_builtin(), builder_id=f"object:{old.logical_resource_id}", dependency_type="aggregate")\n')
            for name in ["sync", "verify"]:
                code, result = command(name)
                self.assertEqual(code, 0, result)
            text = (project / "docs/views/A.md").read_text()
            self.assertIn("## Execution", text)
            self.assertIn("**Budget:** 50", text)

    def make_plan(self, values=None):
        fields, calls = FieldPlan(), []
        fields.document("A", "resource://inputs/A")
        fields.document("C", "resource://inputs/C")
        fields.input("C", "rate", "resource://inputs/C#/rate")
        def deadline(ctx, plan):
            calls.append("deadline")
            return ctx.read("resource://inputs/B#/finish")
        def total(ctx, plan):
            calls.append("total")
            return plan.read_path(ctx, "A", "/plan/deadline") * plan.read(ctx, "C", "rate")
        def budget(ctx, plan):
            calls.append("budget")
            return plan.read(ctx, "C", "total")
        fields.computed_path("A", "/plan/deadline", "resource://fields/deadline", deadline)
        fields.computed("C", "total", "resource://fields/total", total)
        fields.computed_path("A", "/plan/budget", "resource://fields/budget", budget,
                             raw_override="resource://inputs/A#/plan/budget")
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A"))
        store = MemoryStore(values or {"inputs.A": {"plan": {"note": "keep"}}, "inputs.B": {"finish": 10}, "inputs.C": {"rate": 5}})
        return fields, calls, registry, store

    def test_nested_demand_and_complete_parent_composition(self):
        fields, calls, registry, store = self.make_plan()
        engine = BuildEngine(store, registry)
        self.assertEqual(engine.build("resource://fields/deadline").to_builtin(), {"value": 10})
        self.assertEqual(calls, ["deadline"])
        calls.clear()
        self.assertEqual(engine.build("resource://fields/budget").to_builtin(), {"value": 50})
        self.assertEqual(calls, ["budget", "total", "deadline"])
        calls.clear()
        registry.register("resource://views/plan", lambda ctx: {"plan": fields.read_path(ctx, "A", "/plan")})
        self.assertEqual(engine.build("resource://views/plan").to_builtin(), {"plan": {"note": "keep", "deadline": 10, "budget": 50}})
        self.assertEqual(collections.Counter(calls), {"deadline": 1, "total": 1, "budget": 1})
        self.assertEqual(store.objects["inputs.A"].to_builtin(), {"plan": {"note": "keep"}})

    def test_atomic_subtree_and_parent_self_demand(self):
        fields = FieldPlan()
        fields.document("A", "resource://inputs/A")
        fields.computed_path("A", "/bundle", "resource://fields/bundle", lambda ctx, p: {"nested": {"x": 7}})
        with self.assertRaisesRegex(FieldPlanError, "overlapping"):
            fields.computed_path("A", "/bundle/nested/x", "resource://fields/x", lambda ctx, p: 8)
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/x", lambda ctx: {"value": fields.read_path(ctx, "A", "/bundle/nested/x")})
        self.assertEqual(BuildEngine(MemoryStore({"inputs.A": {}}), registry).build("resource://views/x").to_builtin(), {"value": 7})
        other = FieldPlan()
        other.document("A", "resource://inputs/A")
        other.computed_path("A", "/plan/budget", "resource://fields/budget", lambda ctx, p: p.read_path(ctx, "A", "/plan"))
        reg = BuilderRegistry()
        other.register(reg)
        with self.assertRaises(BuildCycleError):
            BuildEngine(MemoryStore({"inputs.A": {}}), reg).build("resource://fields/budget")
        collision = FieldPlan()
        collision.document("A", "resource://inputs/A")
        collision.computed_path("A", "/x", "resource://fields/x", lambda ctx, p: 1)
        reg = BuilderRegistry()
        reg.register(collision.object_target("A", ""), lambda ctx: {})
        with self.assertRaisesRegex(FieldPlanError, "target collision"):
            collision.register(reg)
        wrong_override = FieldPlan()
        wrong_override.document("A", "resource://inputs/A")
        wrong_override.computed_path("A", "/x", "resource://fields/x", lambda ctx, p: 1,
                                     raw_override="resource://inputs/B#/x")
        with self.assertRaisesRegex(FieldPlanError, "differs from canonical binding"):
            wrong_override.register(BuilderRegistry())

    def test_paths_shapes_arrays_and_legacy_names(self):
        fields = FieldPlan()
        fields.document("A", "resource://inputs/A")
        entries = [("/new/deep/value", 3), ("/items/0/value", 4), ("/numeric/0/value", 5), ("/a~1~0/", 6)]
        for index, (path, value) in enumerate(entries):
            fields.computed_path("A", path, f"resource://fields/f{index}", lambda ctx, p, v=value: v)
        fields.computed("A", "plan.deadline", "resource://fields/dot", lambda ctx, p: 7)
        registry = BuilderRegistry()
        fields.register(registry)
        registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A"))
        raw = {"items": [{"keep": True}], "numeric": {"0": {}}, "untouched": [1, 2]}
        result = BuildEngine(MemoryStore({"inputs.A": raw}), registry).build("resource://views/A").to_builtin()
        self.assertEqual(result, {**raw, "new": {"deep": {"value": 3}}, "items": [{"keep": True, "value": 4}], "numeric": {"0": {"value": 5}}, "a/~": {"": 6}, "plan.deadline": 7})
        for broken in [{"items": []}, {"items": [{"value": 4}]}, {"items": [None]}, {"new": None, "items": [{}]}]:
            with self.subTest(broken=broken), self.assertRaises(FieldPlanError):
                BuildEngine(MemoryStore({"inputs.A": broken}), registry).build("resource://views/A")

    def test_nested_override_presence_and_conflicts(self):
        for value in [None, False, 0, "", [], {}]:
            fields, calls, registry, store = self.make_plan({"inputs.A": {"plan": {"budget": value}}, "inputs.B": {"finish": 10}, "inputs.C": {"rate": 5}})
            self.assertEqual(BuildEngine(store, registry).build("resource://fields/budget").to_builtin(), {"value": value})
            self.assertEqual(calls, [])
        fields, calls, registry, store = self.make_plan({"inputs.A": {"plan": {"deadline": 99}}, "inputs.B": {"finish": 10}, "inputs.C": {"rate": 5}})
        with self.assertRaisesRegex(FieldPlanError, "raw field conflicts"):
            BuildEngine(store, registry).build("resource://fields/deadline")
        with self.assertRaisesRegex(FieldPlanError, "duplicate provider"):
            f = FieldPlan()
            f.input_path("A", "/a~1b", "resource://inputs/A#/x")
            f.input_path("A", "/a~1b", "resource://inputs/A#/y")

    def test_nested_graphs_against_independent_topological_oracle(self):
        rng = random.Random(41)
        for case in range(40):
            graph = {i: rng.sample(list(range(i)), rng.randrange(min(i, 3) + 1)) for i in range(12)}
            expected = {}
            for i in graphlib.TopologicalSorter(graph).static_order():
                expected[i] = i + sum(expected[d] for d in graph[i])
            fields = FieldPlan()
            fields.document("A", "resource://inputs/A")
            declaration_order = list(graph)
            rng.shuffle(declaration_order)
            for i in declaration_order:
                fields.computed_path("A", f"/sections/s{i}/value", f"resource://fields/f{i}",
                                     lambda ctx, p, n=i: n + sum(p.read_path(ctx, "A", f"/sections/s{d}/value") for d in graph[n]))
            registry = BuilderRegistry()
            fields.register(registry)
            registry.register("resource://views/A", lambda ctx: fields.compose(ctx, "A"))
            result = BuildEngine(MemoryStore({"inputs.A": {}}), registry).build("resource://views/A").to_builtin()
            self.assertEqual({i: result["sections"][f"s{i}"]["value"] for i in graph}, expected, case)

    def test_nested_cli_fixture_and_current_flat_state_adoption(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "nested"
            shutil.copytree(FIXTURE, project)
            for name in ["sync", "verify"]:
                code, result = run_json([name, "--project-root", str(project), "--json"])
                self.assertEqual(code, 0, result)
            text = (project / "docs/views/A.md").read_text()
            self.assertIn("**Budget:** 50", text)
            self.assertIn("**Deadline:** 10", text)
            self.assertIn('<a id="migration-plan"></a>', text)
            # Adopt an existing populated project without renaming field targets.
            flat = Path(tmp) / "flat"
            shutil.copytree(ROOT / "examples/field_dependency_project", flat)
            shutil.copyfile(ROOT / "tests/fixtures/field_plan_v1.py.txt", flat / "docengine_project/fields.py")
            code, result = run_json(["sync", "--project-root", str(flat), "--json"])
            self.assertEqual(code, 0, result)
            state_before = json.loads((flat / "docs/_dependency/state/dependency_state.json").read_text())
            previous_receipts = {p.relative_to(flat): p.read_bytes() for p in (flat / "docs/_dependency/receipts").rglob("*.json")}
            shutil.copyfile(ROOT / "examples/field_dependency_project/docengine_project/fields.py", flat / "docengine_project/fields.py")
            for name in ["sync", "verify"]:
                code, result = run_json([name, "--project-root", str(flat), "--json"])
                self.assertEqual(code, 0, result)
            state_after = json.loads((flat / "docs/_dependency/state/dependency_state.json").read_text())
            self.assertEqual(set(state_before["targets"]), set(state_after["targets"]))
            self.assertNotEqual(state_before, state_after)  # code revision is new evidence
            for path, content in previous_receipts.items():
                self.assertEqual((flat / path).read_bytes(), content)
