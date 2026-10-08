import pytest
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from docengine.builders import BuildEngine
from docengine.config import ProjectConfigError, load_project_config
from docengine.extensions import ProjectExtensionError, load_project_extension
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample_project"
PRODUCT = ROOT / "examples" / "product_tax_project"


class ProjectExtensionTests(unittest.TestCase):
    def _load(self, project: Path):
        roots = discover_roots(project_root=project)
        catalog = ResourceCatalog.scan(roots)
        extension = load_project_extension(roots, catalog)
        return roots, catalog, extension

    def test_sample_project_builder_is_loaded_and_tracks_fields(self):
        _, catalog, extension = self._load(SAMPLE)
        result = BuildEngine(catalog, extension.registry).build("resource://architecture/system_summary")
        self.assertEqual(result.to_builtin()["allowed_method_count"], 2)
        self.assertEqual(
            [str(dep.ref) for dep in result.provenance.dependencies],
            [
                "resource://architecture/overview#/title",
                "resource://policies/method_policy#/allowed_methods",
            ],
        )
        self.assertTrue(result.provenance.audit_complete)

    def test_unrelated_product_tax_fixture_uses_same_runtime(self):
        _, catalog, extension = self._load(PRODUCT)
        result = BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax")
        self.assertEqual(result.to_builtin(), {"price": 100, "tax_rate": 0.2, "total": 120.0})
        refs = [str(dep.ref) for dep in result.provenance.dependencies]
        self.assertEqual(refs, ["resource://catalog/product#/price", "resource://catalog/tax_policy#/rate"])
        self.assertNotIn("resource://catalog/product#/unused_note", refs)

    @pytest.mark.requires_symlink
    def test_project_package_must_be_confined_local_package(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            shutil.rmtree(project / "docengine_project")
            outside = Path(outside_tmp) / "outside_package"
            outside.mkdir()
            (outside / "__init__.py").write_text("def register_builders(registry): pass\n", encoding="utf-8")
            (project / "docengine_project").symlink_to(outside, target_is_directory=True)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "must not be symlinks"):
                load_project_extension(roots, catalog)

    def test_registered_target_must_have_derived_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                "def register_builders(registry):\n"
                "    registry.register('resource://catalog/product', lambda ctx: {'x': 1})\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "derived_descriptor"):
                load_project_extension(roots, catalog)

    def test_internal_target_without_descriptor_is_allowed_but_existing_derived_descriptors_still_need_builders(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                "def register_builders(registry):\n"
                "    registry.register('resource://internal/missing', lambda ctx: {'x': 1})\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "derived descriptor .* has no registered builder"):
                load_project_extension(roots, catalog)

    def test_project_package_name_is_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docengine.toml").write_text(
                "[docengine]\nconfig_version=1\n"
                'documentation_root="docs"\nstructured_dir="_structured"\ndependency_dir="_dependency"\n'
                'project_package="../evil"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProjectConfigError, "canonical dotted"):
                load_project_config(root)

    def test_derived_object_envelope_validates_against_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        _, catalog, extension = self._load(PRODUCT)
        result = BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax")
        schema = json.loads((ROOT / "spec/schemas/DERIVED_OBJECT.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(result.to_envelope(), schema)


if __name__ == "__main__":
    unittest.main()

class ProjectExtensionTreeSafetyTests(unittest.TestCase):
    @pytest.mark.requires_symlink
    def test_symlinked_submodule_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            outside = Path(outside_tmp) / "builders.py"
            outside.write_text("def register(registry): pass\n", encoding="utf-8")
            builders = project / "docengine_project/builders.py"
            builders.unlink()
            builders.symlink_to(outside)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "contains symlinked"):
                load_project_extension(roots, catalog)

class ProjectExtensionOwnershipTests(unittest.TestCase):
    def test_project_package_cannot_live_inside_documentation_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            embedded = project / "docs/project_code"
            embedded.mkdir()
            (project / "docs/__init__.py").write_text("", encoding="utf-8")
            (embedded / "__init__.py").write_text("def register_builders(registry): pass\n", encoding="utf-8")
            config = project / "docengine.toml"
            config.write_text(config.read_text(encoding="utf-8").replace('project_package = "docengine_project"', 'project_package = "docs.project_code"'), encoding="utf-8")
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "outside the documentation root"):
                load_project_extension(roots, catalog)

class NestedProjectPackageTests(unittest.TestCase):
    def test_dotted_package_requires_all_parent_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            nested = project / "company/builders"
            nested.mkdir(parents=True)
            (nested / "__init__.py").write_text("def register_builders(registry): pass\n", encoding="utf-8")
            config = project / "docengine.toml"
            config.write_text(config.read_text(encoding="utf-8").replace('project_package = "docengine_project"', 'project_package = "company.builders"'), encoding="utf-8")
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "importable local package"):
                load_project_extension(roots, catalog)

class InternalDerivedAndDescriptorIntegrityTests(unittest.TestCase):
    def test_internal_derived_target_does_not_require_documentation_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                "def register_builders(registry):\n"
                "    registry.register('resource://internal/helper', lambda ctx: {'x': 1})\n"
                "    registry.register('resource://catalog/price_with_tax', lambda ctx: {'total': 120})\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            result = BuildEngine(catalog, extension.registry).build("resource://internal/helper")
            self.assertEqual(result.to_builtin(), {"x": 1})

    def test_derived_descriptor_without_builder_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            (project / "docengine_project/__init__.py").write_text(
                "def register_builders(registry):\n    pass\n",
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            with self.assertRaisesRegex(ProjectExtensionError, "has no registered builder"):
                load_project_extension(roots, catalog)


class DottedProjectPackageRuntimeTests(unittest.TestCase):
    def test_dotted_package_supports_parent_relative_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            shutil.rmtree(project / "docengine_project")
            package = project / "company"
            builders = package / "builders"
            builders.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "common.py").write_text("TOTAL = 120\n", encoding="utf-8")
            (builders / "__init__.py").write_text(
                "from ..common import TOTAL\n"
                "def register_builders(registry):\n"
                "    registry.register('resource://catalog/price_with_tax', lambda ctx: {'total': TOTAL})\n",
                encoding="utf-8",
            )
            config = project / "docengine.toml"
            config.write_text(
                config.read_text(encoding="utf-8").replace('project_package = "docengine_project"', 'project_package = "company.builders"'),
                encoding="utf-8",
            )
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            result = BuildEngine(catalog, extension.registry).build("resource://catalog/price_with_tax")
            self.assertEqual(result.to_builtin(), {"total": 120})
            self.assertTrue(extension.source_revision.startswith("sha256:"))
            self.assertEqual(result.provenance.builder_revision, extension.source_revision)

    def test_dotted_parent_import_of_configured_child_does_not_execute_child_twice(self):
        import builtins
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            config = project / "docengine.toml"
            config.write_text(
                config.read_text(encoding="utf-8")
                .replace('project_package = "docengine_project"', 'project_package = "company.builders"')
                .replace('docengine_project/schemas/', 'company/schemas/'),
                encoding="utf-8",
            )
            schemas = project / "docengine_project/schemas"
            (project / "company").mkdir(parents=True)
            shutil.copytree(schemas, project / "company/schemas")
            shutil.rmtree(project / "docengine_project")
            (project / "company/builders").mkdir(parents=True)
            (project / "company/__init__.py").write_text("from . import builders\n", encoding="utf-8")
            (project / "company/builders/__init__.py").write_text(
                "import builtins\n"
                "builtins._docengine_double_exec_probe = getattr(builtins, '_docengine_double_exec_probe', 0) + 1\n"
                "def register_builders(registry):\n"
                "    registry.register('resource://architecture/system_summary', lambda ctx: {'title': 'ok'})\n",
                encoding="utf-8",
            )
            if hasattr(builtins, "_docengine_double_exec_probe"):
                delattr(builtins, "_docengine_double_exec_probe")
            try:
                roots = discover_roots(project_root=project)
                catalog = ResourceCatalog.scan(roots)
                load_project_extension(roots, catalog)
                self.assertEqual(getattr(builtins, "_docengine_double_exec_probe"), 1)
            finally:
                if hasattr(builtins, "_docengine_double_exec_probe"):
                    delattr(builtins, "_docengine_double_exec_probe")

    def test_project_source_revision_changes_when_builder_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            first = load_project_extension(roots, catalog)
            builders = project / "docengine_project/builders.py"
            builders.write_text(builders.read_text(encoding="utf-8") + "\n# revision change\n", encoding="utf-8")
            second = load_project_extension(roots, ResourceCatalog.scan(roots))
            self.assertNotEqual(first.source_revision, second.source_revision)
