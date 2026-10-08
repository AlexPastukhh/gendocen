import pytest
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docengine.cli import main
from docengine.project import discover_roots
from docengine.objects import RawObject
from docengine.resources import ResourceCatalog, ResourceError


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "examples" / "sample_project"
PRODUCT = REPO_ROOT / "examples" / "product_tax_project"


class P1ResourceTests(unittest.TestCase):
    def _copy_sample(self, root: Path) -> Path:
        target = root / "project"
        shutil.copytree(SAMPLE, target)
        return target

    def test_sample_catalog_distinguishes_all_four_inventory_kinds(self):
        roots = discover_roots(project_root=SAMPLE)
        catalog = ResourceCatalog.scan(roots)
        kinds = {item.kind for item in catalog.items}
        self.assertEqual(kinds, {"plain", "managed", "derived", "generated"})
        self.assertEqual(catalog.resolve("resource://policies/method_policy#/allowed_methods/1"), "method_b")
        self.assertIsInstance(catalog.resolve("resource://policies/method_policy"), RawObject)
        self.assertEqual(
            catalog.version("resource://policies/method_policy#/allowed_methods/1"),
            catalog.version("resource://policies/method_policy#/allowed_methods/1"),
        )
        rationale = catalog.resolve("file://architecture/rationale.md")
        self.assertIn("Rationale", rationale)

    def test_resources_json_is_deterministic(self):
        outputs = []
        for _ in range(2):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["resources", "--project-root", str(SAMPLE), "--json"])
            self.assertEqual(code, 0)
            outputs.append(stream.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        payload = json.loads(outputs[0])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["meta"]["status"], "ok")
        self.assertEqual(payload["data"]["counts"], {"derived": 1, "generated": 3, "managed": 2, "plain": 1})

    def test_resources_human_output_is_deterministic(self):
        outputs = []
        for _ in range(2):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["resources", "--project-root", str(SAMPLE)])
            self.assertEqual(code, 0)
            outputs.append(stream.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("PLAIN", outputs[0])
        self.assertIn("MANAGED", outputs[0])
        self.assertIn("DERIVED", outputs[0])
        self.assertIn("GENERATED", outputs[0])

    def test_plain_markdown_needs_no_json_sidecar(self):
        roots = discover_roots(project_root=SAMPLE)
        catalog = ResourceCatalog.scan(roots)
        rationale = [item for item in catalog.items if item.source == "architecture/rationale.md"]
        self.assertEqual(len(rationale), 1)
        self.assertEqual(rationale[0].kind, "plain")

    def test_schema_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            policy = project / "docs/_structured/policies/method_policy.json"
            data = json.loads(policy.read_text(encoding="utf-8"))
            data["data"]["allowed_methods"] = []
            policy.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "schema validation failed"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_materialization_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["materialize"][0]["path"] = "../outside.md"
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "unsafe materialization path"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_duplicate_resource_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            duplicate = project / "docs/_structured/architecture/duplicate.json"
            data = json.loads((project / "docs/_structured/architecture/overview.json").read_text(encoding="utf-8"))
            data["$docengine"]["materialize"][0]["path"] = "architecture/duplicate.md"
            duplicate.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "duplicate resource_id"):
                ResourceCatalog.scan(discover_roots(project_root=project))


    def test_mirrored_structured_layout_is_enforced_for_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["materialize"][0]["path"] = "architecture/not_overview.md"
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "mirrored _structured convention"):
                ResourceCatalog.scan(discover_roots(project_root=project))


    def test_noncanonical_materialization_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["materialize"][0]["path"] = "architecture//overview.md"
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "must already be canonical"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_invalid_resource_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["resource_id"] = "invalid single"
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "invalid resource_id"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_duplicate_json_keys_in_managed_resource_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            overview.write_text(
                '{"$docengine":{"resource_id":"architecture.overview","materialize":[]},'
                '"data":{"title":"A","title":"B"}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ResourceError, "duplicate JSON object key"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_unknown_declared_schema_fails_instead_of_being_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_sample(Path(tmp))
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["schema"] = "example://schemas/unknown/v1"
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "schema URI is not registered"):
                ResourceCatalog.scan(discover_roots(project_root=project))

class P1ResourceSymlinkSafetyTests(unittest.TestCase):
    @pytest.mark.requires_symlink
    def test_plain_markdown_symlink_outside_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            outside = Path(outside_tmp) / "outside.md"
            outside.write_text("# outside\n", encoding="utf-8")
            (project / "docs/leak.md").symlink_to(outside)
            with self.assertRaisesRegex(ResourceError, "escapes documentation root through symlink"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    @pytest.mark.requires_symlink
    def test_structured_directory_symlink_outside_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_structured")
            outside = Path(outside_tmp) / "structured"
            outside.mkdir()
            (project / "docs/_structured").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ResourceError, "structured resource directory escapes"):
                ResourceCatalog.scan(discover_roots(project_root=project))

class P1ReservedMaterializationSafetyTests(unittest.TestCase):
    def test_materialization_cannot_target_dependency_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["materialize"] = [{
                "renderer": "json",
                "path": "_dependency/state/overwrite.json",
                "path_base": "documentation_root",
            }]
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "reserved dependency state"):
                ResourceCatalog.scan(discover_roots(project_root=project))

    def test_materialization_cannot_target_structured_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            overview = project / "docs/_structured/architecture/overview.json"
            data = json.loads(overview.read_text(encoding="utf-8"))
            data["$docengine"]["materialize"] = [{
                "renderer": "json",
                "path": "_structured/generated.json",
                "path_base": "documentation_root",
            }]
            overview.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ResourceError, "reserved structured state"):
                ResourceCatalog.scan(discover_roots(project_root=project))

class DerivedDescriptorBoundaryTests(unittest.TestCase):
    def test_derived_descriptor_is_inventory_metadata_not_raw_domain_value(self):
        roots = discover_roots(project_root=SAMPLE)
        catalog = ResourceCatalog.scan(roots)
        with self.assertRaisesRegex(ResourceError, "metadata-only"):
            catalog.get("resource://architecture/system_summary")
        with self.assertRaisesRegex(ResourceError, "metadata-only"):
            catalog.version("resource://architecture/system_summary")


class PlainFileReferenceBoundaryTests(unittest.TestCase):
    def test_file_refs_cannot_bypass_structured_resource_boundary(self):
        roots = discover_roots(project_root=SAMPLE)
        catalog = ResourceCatalog.scan(roots)
        with self.assertRaisesRegex(ResourceError, "plain canonical Markdown"):
            catalog.resolve("file://_structured/architecture/overview.json")
        with self.assertRaisesRegex(ResourceError, "plain canonical Markdown"):
            catalog.version("file://_structured/architecture/overview.json")

    def test_file_refs_cannot_use_generated_markdown_as_canonical_input(self):
        roots = discover_roots(project_root=SAMPLE)
        catalog = ResourceCatalog.scan(roots)
        with self.assertRaisesRegex(ResourceError, "plain canonical Markdown"):
            catalog.resolve("file://architecture/overview.md")

class WholeResourceDependencyVersionTests(unittest.TestCase):
    def test_whole_resource_version_tracks_domain_data_not_json_metadata_or_formatting(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            roots = discover_roots(project_root=project)
            before = ResourceCatalog.scan(roots)
            ref = "resource://catalog/product"
            version_before = before.version(ref)
            data_before = before.resolve(ref).to_builtin()

            path = project / "docs/_structured/catalog/product.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["$docengine"]["materialize"].append(
                {"renderer": "json", "path": "exports/product.json", "path_base": "documentation_root"}
            )
            # Reformat/reorder physical JSON and change engine metadata only.
            path.write_text(json.dumps(payload, indent=4, sort_keys=True), encoding="utf-8")
            metadata_only = ResourceCatalog.scan(discover_roots(project_root=project))
            self.assertEqual(metadata_only.resolve(ref).to_builtin(), data_before)
            self.assertEqual(metadata_only.version(ref), version_before)

            payload["data"]["price"] = payload["data"]["price"] + 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            data_changed = ResourceCatalog.scan(discover_roots(project_root=project))
            self.assertNotEqual(data_changed.version(ref), version_before)
