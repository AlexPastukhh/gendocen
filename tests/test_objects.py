import tempfile
import unittest
from pathlib import Path

from docengine.objects import FrozenMapping, RawObject
from docengine.refs import ResourceRef


class RawObjectTests(unittest.TestCase):
    def test_raw_object_is_deeply_immutable_and_pointer_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = RawObject.create(
                resource_id="demo.item",
                source_path=Path(tmp) / "item.json",
                schema_uri=None,
                resource_kind="structured",
                data={"name": "A", "nested": {"x": 1}, "items": ["a", "b"]},
            )
            self.assertIsInstance(raw.data, FrozenMapping)
            self.assertEqual(raw.read("resource://demo/item#/nested/x"), 1)
            self.assertEqual(raw.read(ResourceRef.parse("resource://demo/item#/items/1")), "b")
            for pointer in ("/items/-1", "/items/01", "/items/-"):
                with self.subTest(pointer=pointer), self.assertRaises(KeyError):
                    raw.read(ResourceRef.from_resource_id("demo.item", pointer))
            with self.assertRaises(TypeError):
                raw.data["name"] = "B"  # type: ignore[index]
            with self.assertRaises(TypeError):
                raw.data["nested"]["x"] = 2  # type: ignore[index]
            self.assertEqual(raw.to_builtin()["nested"]["x"], 1)
