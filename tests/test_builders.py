import hashlib
import json
import unittest
from pathlib import Path

from docengine.builders import (
    BuildCycleError,
    BuildEngine,
    BuilderExecutionError,
    BuilderRegistrationError,
    BuilderRegistry,
    DerivedObject,
)
from docengine.objects import RawObject, thaw
from docengine.refs import ResourceRef


class MemoryStore:
    def __init__(self, values):
        self.objects = {
            resource_id: RawObject.create(
                resource_id=resource_id,
                source_path=Path(f"/{resource_id}.json"),
                schema_uri=None,
                resource_kind="structured",
                data=data,
            )
            for resource_id, data in values.items()
        }

    def get(self, ref):
        ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        if ref.scheme != "resource":
            raise KeyError(ref)
        obj = self.objects[ref.logical_resource_id]
        return obj if not ref.pointer_parts else obj.read(ref)

    def version(self, ref):
        ref = ResourceRef.parse(ref) if isinstance(ref, str) else ref
        value = self.get(ref)
        if isinstance(value, RawObject):
            value = value.data
        payload = json.dumps(thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        return hashlib.sha256(payload).hexdigest()


class BuilderRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore({
            "raw.a": {"x": 2, "unused": 999},
            "raw.b": {"y": 3, "unused": "ignore"},
        })

    def test_builder_creates_new_derived_object_without_mutating_raw(self):
        registry = BuilderRegistry()
        before = self.store.objects["raw.a"].to_builtin()

        def build_sum(ctx):
            return {"sum": ctx.read("resource://raw/a#/x") + ctx.read("resource://raw/b#/y")}

        registry.register("resource://derived/sum", build_sum)
        result = BuildEngine(self.store, registry).build("resource://derived/sum")
        self.assertIsInstance(result, DerivedObject)
        self.assertEqual(result.to_builtin(), {"sum": 5})
        self.assertEqual(self.store.objects["raw.a"].to_builtin(), before)
        self.assertIsNot(result, self.store.objects["raw.a"])

    def test_only_actual_tracked_reads_appear_in_dependency_evidence(self):
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/sum",
            lambda ctx: {"sum": ctx.read("resource://raw/a#/x") + ctx.read("resource://raw/b#/y")},
        )
        result = BuildEngine(self.store, registry).build("resource://derived/sum")
        refs = [str(item.ref) for item in result.provenance.dependencies]
        self.assertEqual(refs, ["resource://raw/a#/x", "resource://raw/b#/y"])
        self.assertNotIn("resource://raw/a#/unused", refs)
        self.assertTrue(result.provenance.audit_complete)

    def test_raw_derived_and_derived_derived_chains(self):
        registry = BuilderRegistry()

        registry.register(
            "resource://derived/c",
            lambda ctx: {"sum": ctx.read("resource://raw/a#/x") + ctx.read("resource://raw/b#/y")},
            builder_id="c",
        )
        registry.register(
            "resource://derived/d",
            lambda ctx: {"value": ctx.read("resource://derived/c#/sum") * ctx.read("resource://raw/a#/x")},
            builder_id="d",
        )
        registry.register(
            "resource://derived/e",
            lambda ctx: {
                "total": ctx.read("resource://derived/c#/sum") + ctx.read("resource://derived/d#/value")
            },
            builder_id="e",
        )
        result = BuildEngine(self.store, registry).build("resource://derived/e")
        self.assertEqual(result.to_builtin(), {"total": 15})
        self.assertEqual(
            [str(dep.ref) for dep in result.provenance.dependencies],
            ["resource://derived/c#/sum", "resource://derived/d#/value"],
        )
        self.assertTrue(all(dep.source_kind == "derived" for dep in result.provenance.dependencies))

    def test_get_tracks_whole_resource_and_returns_object(self):
        registry = BuilderRegistry()

        def build(ctx):
            raw = ctx.get("resource://raw/a")
            return {"copy": raw.read("resource://raw/a#/x")}

        registry.register("resource://derived/whole", build)
        result = BuildEngine(self.store, registry).build("resource://derived/whole")
        self.assertEqual([str(dep.ref) for dep in result.provenance.dependencies], ["resource://raw/a"])

    def test_cycle_is_deterministic_and_explains_exact_path(self):
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/a",
            lambda ctx: {"v": ctx.read("resource://derived/b#/v")},
            builder_id="a",
        )
        registry.register(
            "resource://derived/b",
            lambda ctx: {"v": ctx.read("resource://derived/a#/v")},
            builder_id="b",
        )
        engine = BuildEngine(self.store, registry)
        expected = (
            "resource://derived/a",
            "resource://derived/b",
            "resource://derived/a",
        )
        for _ in range(2):
            with self.assertRaises(BuildCycleError) as raised:
                engine.build("resource://derived/a")
            self.assertEqual(raised.exception.cycle, expected)
            self.assertIn("resource://derived/a -> resource://derived/b -> resource://derived/a", str(raised.exception))

    def test_repeated_build_has_equivalent_output_and_provenance(self):
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/sum",
            lambda ctx: {"sum": ctx.read("resource://raw/a#/x") + ctx.read("resource://raw/b#/y")},
            builder_id="sum",
            dependency_type="compute",
            comparator="exact",
        )
        engine = BuildEngine(self.store, registry)
        first = engine.build("resource://derived/sum")
        second = engine.build("resource://derived/sum")
        self.assertEqual(first, second)
        self.assertEqual(first.provenance.provenance_digest, second.provenance.provenance_digest)

    def test_untracked_escape_hatch_is_explicit_and_marks_audit_incomplete(self):
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/untracked",
            lambda ctx: {"x": ctx.untracked_read("resource://raw/a#/x", reason="legacy helper")},
        )
        result = BuildEngine(self.store, registry).build("resource://derived/untracked")
        self.assertEqual(result.provenance.dependencies, ())
        self.assertFalse(result.provenance.audit_complete)
        self.assertEqual(result.provenance.untracked_accesses[0].reason, "legacy helper")

    def test_untracked_read_requires_reason(self):
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/untracked",
            lambda ctx: {"x": ctx.untracked_read("resource://raw/a#/x", reason="")},
        )
        with self.assertRaisesRegex(BuilderExecutionError, "non-empty reason"):
            BuildEngine(self.store, registry).build("resource://derived/untracked")

    def test_emit_is_supported_but_cannot_be_mixed_with_return_value(self):
        registry = BuilderRegistry()

        def emit_only(ctx):
            ctx.emit({"x": 1})

        registry.register("resource://derived/emitted", emit_only)
        self.assertEqual(BuildEngine(self.store, registry).build("resource://derived/emitted").to_builtin(), {"x": 1})

        registry2 = BuilderRegistry()

        def bad(ctx):
            ctx.emit({"x": 1})
            return {"x": 2}

        registry2.register("resource://derived/bad", bad)
        with self.assertRaisesRegex(BuilderExecutionError, "either return an output or call ctx.emit"):
            BuildEngine(self.store, registry2).build("resource://derived/bad")

    def test_registry_decorator_is_convenience_over_explicit_registry(self):
        registry = BuilderRegistry()

        @registry.builder("resource://derived/decorated", builder_id="decorated")
        def decorated(ctx):
            return {"x": ctx.read("resource://raw/a#/x")}

        self.assertEqual(registry.get("resource://derived/decorated").function, decorated)
        self.assertEqual(registry.get("resource://derived/decorated").builder_id, "decorated")

    def test_duplicate_target_and_invalid_dependency_type_are_rejected(self):
        registry = BuilderRegistry()
        registry.register("resource://derived/a", lambda ctx: {"x": 1})
        with self.assertRaisesRegex(BuilderRegistrationError, "already registered"):
            registry.register("resource://derived/a", lambda ctx: {"x": 2})
        with self.assertRaisesRegex(BuilderRegistrationError, "dependency_type"):
            registry.register("resource://derived/b", lambda ctx: {"x": 2}, dependency_type="semantic_review")


if __name__ == "__main__":
    unittest.main()

class BuilderOutputValidationTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore({"raw.a": {"x": 1}})

    def test_builder_output_is_copied_into_immutable_derived_value(self):
        registry = BuilderRegistry()
        mutable = {"items": [1, 2]}
        registry.register("resource://derived/copied", lambda ctx: mutable)
        result = BuildEngine(self.store, registry).build("resource://derived/copied")
        mutable["items"].append(3)
        self.assertEqual(result.to_builtin(), {"items": [1, 2]})
        with self.assertRaises(TypeError):
            result.data["other"] = 1  # type: ignore[index]

    def test_non_json_builder_outputs_are_rejected(self):
        for value in ({1: "bad-key"}, {"bad": float("nan")}, {"bad": object()}):
            with self.subTest(value=repr(value)):
                registry = BuilderRegistry()
                registry.register("resource://derived/bad", lambda ctx, value=value: value)
                with self.assertRaises(BuilderExecutionError):
                    BuildEngine(self.store, registry).build("resource://derived/bad")

class TransitiveAuditCompletenessTests(unittest.TestCase):
    def test_upstream_untracked_access_propagates_incomplete_audit(self):
        store = MemoryStore({"raw.a": {"x": 4}})
        registry = BuilderRegistry()
        registry.register(
            "resource://derived/upstream",
            lambda ctx: {"x": ctx.untracked_read("resource://raw/a#/x", reason="legacy")},
        )
        registry.register(
            "resource://derived/downstream",
            lambda ctx: {"y": ctx.read("resource://derived/upstream#/x") * 2},
        )
        result = BuildEngine(store, registry).build("resource://derived/downstream")
        self.assertFalse(result.provenance.audit_complete)
        self.assertEqual(len(result.provenance.dependencies), 1)
        self.assertFalse(result.provenance.dependencies[0].source_audit_complete)

class DependencyComparatorAndAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore({
            "raw.a": {"x": 2, "tags": ["a", "b"]},
            "raw.b": {"y": 3},
        })

    def test_dependency_comparator_can_vary_per_read_with_builder_default(self):
        registry = BuilderRegistry(source_revision="sha256:test")

        def build(ctx):
            x = ctx.read("resource://raw/a#/x")
            tags = ctx.read("resource://raw/a#/tags", comparator="set")
            return {"x": x, "tags": list(tags)}

        registry.register("resource://derived/mixed", build, comparator="exact")
        result = BuildEngine(self.store, registry).build("resource://derived/mixed")
        evidence = {str(item.ref): item.comparator for item in result.provenance.dependencies}
        self.assertEqual(evidence["resource://raw/a#/x"], "exact")
        self.assertEqual(evidence["resource://raw/a#/tags"], "set")
        self.assertEqual(result.provenance.builder_revision, "sha256:test")
        self.assertEqual(result.provenance.tracking_assurance, "cooperative")

    def test_same_ref_cannot_be_recorded_with_conflicting_comparators_in_one_build(self):
        registry = BuilderRegistry()

        def build(ctx):
            ctx.read("resource://raw/a#/x", comparator="exact")
            ctx.read("resource://raw/a#/x", comparator="json_structured")
            return {"x": 2}

        registry.register("resource://derived/conflict", build)
        with self.assertRaisesRegex(BuilderExecutionError, "dependency evidence changed"):
            BuildEngine(self.store, registry).build("resource://derived/conflict")
