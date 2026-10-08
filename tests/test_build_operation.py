"""Stable command scopes, evidence preservation and mutation rejection."""
import collections
import dataclasses
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from docengine.builders import BuildEngine, BuildOperation, BuildSourceChangedError, BuilderError, BuilderRegistry
from docengine.dependencies import DependencyError, DependencyResolver
from docengine.extensions import load_project_extension
from docengine.objects import RawObject
from tests.test_builders import MemoryStore
from tests.test_documentation_workflows import run_json
from tests.test_field_dependency_project import ROOT
from tests.test_field_dependency_project import FieldPlan


class BuildOperationTests(unittest.TestCase):
    def test_observed_change_cannot_be_swallowed_even_if_source_is_restored(self):
        store = MemoryStore({"raw.input": {"x": 1}})
        original = store.objects["raw.input"]
        registry = BuilderRegistry()
        def producer(ctx):
            value = ctx.read("resource://raw/input#/x")
            store.objects["raw.input"] = RawObject.create(resource_id="raw.input", source_path=Path("/raw.json"), schema_uri=None, resource_kind="structured", data={"x": 2})
            try:
                ctx.read("resource://raw/input#/x")
            except BuildSourceChangedError:
                store.objects["raw.input"] = original
            return {"value": value}
        registry.register("resource://fields/one", producer)
        with self.assertRaises(BuildSourceChangedError):
            BuildEngine(store, registry, operation=BuildOperation(store, registry)).build("resource://fields/one")

    def test_recursive_chain_keeps_default_limit_and_handles_128_fields(self):
        import sys
        limit = sys.getrecursionlimit()
        fields = FieldPlan()
        for i in range(128):
            fields.computed("A", f"f{i}", f"resource://fields/f{i}",
                            lambda ctx, p, n=i: 1 if n == 0 else p.read(ctx, "A", f"f{n-1}") + 1)
        registry = BuilderRegistry()
        fields.register(registry)
        store = MemoryStore({})
        result = BuildEngine(store, registry, operation=BuildOperation(store, registry)).build("resource://fields/f127")
        self.assertEqual(result.to_builtin(), {"value": 128})
        self.assertEqual(sys.getrecursionlimit(), limit)

    def test_scoped_cache_fresh_calls_and_project_isolation(self):
        store = MemoryStore({"raw.input": {"x": 3}})
        registry = BuilderRegistry()
        calls = collections.Counter()
        def shared(ctx):
            calls["shared"] += 1
            return {"x": ctx.read("resource://raw/input#/x") * 2}
        registry.register("resource://fields/shared", shared)
        for target in ["a", "b"]:
            registry.register(f"resource://views/{target}", lambda ctx: {"v": ctx.read("resource://fields/shared#/x")})
        operation = BuildOperation(store, registry)
        engine = BuildEngine(store, registry, operation=operation)
        for target in ["a", "b", "a"]:
            self.assertEqual(engine.build(f"resource://views/{target}").to_builtin(), {"v": 6})
        self.assertEqual(calls["shared"], 1)
        BuildEngine(store, registry).build("resource://views/a")
        self.assertEqual(calls["shared"], 2)
        with self.assertRaisesRegex(BuilderError, "different store"):
            BuildEngine(MemoryStore({}), registry, operation=operation)
        with self.assertRaisesRegex(DependencyError, "different catalog/registry"):
            DependencyResolver(MemoryStore({}), registry, operation=operation)
        with self.assertRaisesRegex(DependencyError, "different catalog/registry"):
            DependencyResolver(store, BuilderRegistry(), operation=operation)
        store.objects["raw.input"] = RawObject.create(resource_id="raw.input", source_path=Path("/raw.json"), schema_uri=None, resource_kind="structured", data={"x": 4})
        with self.assertRaises(BuildSourceChangedError):
            engine.build("resource://views/a")
        fresh = BuildEngine(store, registry, operation=BuildOperation(store, registry))
        self.assertEqual(fresh.build("resource://views/b").to_builtin(), {"v": 8})

    def test_failed_producer_is_retryable_and_registry_changes_fail(self):
        registry, calls = BuilderRegistry(), []
        store = MemoryStore({})
        def flaky(ctx):
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("first attempt")
            return {"value": 7}
        registry.register("resource://fields/flaky", flaky)
        engine = BuildEngine(store, registry, operation=BuildOperation(store, registry))
        with self.assertRaises(BuilderError):
            engine.build("resource://fields/flaky")
        self.assertEqual(engine.build("resource://fields/flaky").to_builtin(), {"value": 7})
        registry.register("resource://fields/new", lambda ctx: {})
        with self.assertRaisesRegex(BuildSourceChangedError, "registry changed"):
            engine.build("resource://fields/flaky")

    def test_actual_cli_commands_execute_each_successful_builder_once(self):
        for fixture in ["field_dependency_project", "nested_field_project"]:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(ROOT / "examples" / fixture, project)
                counts = collections.Counter()
                def load(*args, **kwargs):
                    extension = load_project_extension(*args, **kwargs)
                    registry = BuilderRegistry(source_revision=extension.source_revision)
                    registry.bind_revision_check(extension.registry._revision_check)
                    for spec in extension.registry.specs:
                        def wrapped(ctx, spec=spec):
                            counts[str(spec.target)] += 1
                            return spec.function(ctx)
                        registry.register(spec.target, wrapped, builder_id=spec.builder_id,
                                          dependency_type=spec.dependency_type, comparator=spec.comparator)
                    return dataclasses.replace(extension, registry=registry)
                with patch("docengine.cli.load_project_extension", load):
                    for command in ["sync", "sync", "check", "diff", "verify", "materialize"]:
                        counts.clear()
                        argv = [command]
                        if command == "diff":
                            argv += ["resource://views/A"]
                        if command == "materialize":
                            argv += ["--all"]
                        code, result = run_json(argv + ["--project-root", str(project), "--json"])
                        self.assertEqual(code, 0, result)
                        self.assertTrue(counts, command)
                        self.assertEqual(set(counts.values()), {1}, (command, counts))

    def test_mid_operation_source_or_code_mutation_never_publishes_success(self):
        for mutation in ["source", "code"]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp) / "project"
                shutil.copytree(ROOT / "examples/field_dependency_project", project)
                original = load_project_extension
                def load(*args, **kwargs):
                    ext = original(*args, **kwargs)
                    registry = BuilderRegistry(source_revision=ext.source_revision)
                    registry.bind_revision_check(ext.registry._revision_check)
                    changed = []
                    for spec in ext.registry.specs:
                        def mutate(ctx, spec=spec):
                            result = spec.function(ctx)
                            if str(spec.target) == "resource://fields/B_a1" and not changed:
                                changed.append(True)
                                if mutation == "source":
                                    path = project / "docs/_structured/inputs/C.json"
                                    value = json.loads(path.read_text())
                                    value["data"]["x"] = 500
                                    path.write_text(json.dumps(value) + "\n")
                                else:
                                    with (project / "docengine_project/fields.py").open("a") as f:
                                        f.write("\n# changed during operation\n")
                            return result
                        registry.register(spec.target, mutate, builder_id=spec.builder_id)
                    return dataclasses.replace(ext, registry=registry)
                with patch("docengine.cli.load_project_extension", load):
                    code, result = run_json(["sync", "--project-root", str(project), "--json"])
                self.assertEqual(code, 3, result)
                self.assertIn("changed", json.dumps(result))
                self.assertFalse((project / "docs/views/A.md").exists())
                self.assertFalse((project / "docs/_dependency/state/dependency_state.json").exists())
