import tempfile
import unittest
from pathlib import Path

from docengine.project import RootDiscoveryError, confined_path, discover_roots


class ProjectDiscoveryTests(unittest.TestCase):
    def test_explicit_docs_root_must_be_inside_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(RootDiscoveryError):
                discover_roots(project_root=project, docs_root=outside)

    def test_confined_path_rejects_escape(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RootDiscoveryError):
                confined_path(root, "../escape.txt")


    def test_upward_search_finds_docengine_marker(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            (root / "docengine.toml").write_text("", encoding="utf-8")
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            roots = discover_roots(cwd=nested)
            self.assertEqual(roots.project_root, root.resolve())
            self.assertEqual(roots.source, "config_marker")


    def test_explicit_project_root_must_exist_and_be_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing"
            with self.assertRaises(RootDiscoveryError):
                discover_roots(project_root=missing)
            file_root = root / "project-file"
            file_root.write_text("x", encoding="utf-8")
            with self.assertRaises(RootDiscoveryError):
                discover_roots(project_root=file_root)

    def test_existing_documentation_root_must_be_directory(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            docs_file = root / "docs-file"
            docs_file.write_text("x", encoding="utf-8")
            with self.assertRaises(RootDiscoveryError):
                discover_roots(project_root=root, docs_root="docs-file")

    def test_discovery_is_read_only(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            before = sorted(p.relative_to(root) for p in root.rglob("*"))
            roots = discover_roots(project_root=root)
            after = sorted(p.relative_to(root) for p in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(roots.project_root, root.resolve())

class ProjectConfigDiscoveryTests(unittest.TestCase):
    def test_configured_documentation_root_is_used(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            (root / "docengine.toml").write_text(
                '[docengine]\nconfig_version = 1\ndocumentation_root = "documentation"\nstructured_dir = "_structured"\ndependency_dir = "_dependency"\n',
                encoding="utf-8",
            )
            roots = discover_roots(project_root=root)
            self.assertEqual(roots.documentation_root, (root / "documentation").resolve())

    def test_explicit_docs_root_overrides_config_but_stays_confined(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            (root / "docengine.toml").write_text(
                '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\nstructured_dir = "_structured"\ndependency_dir = "_dependency"\n',
                encoding="utf-8",
            )
            roots = discover_roots(project_root=root, docs_root="manual_docs")
            self.assertEqual(roots.documentation_root, (root / "manual_docs").resolve())

class ProjectConfigSafetyTests(unittest.TestCase):
    def test_dangling_config_symlink_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            root = Path(project)
            (root / "docengine.toml").symlink_to(Path(outside) / "missing.toml")
            with self.assertRaises(RootDiscoveryError):
                discover_roots(project_root=root)

class ProjectDiscoveryMalformedMarkerTests(unittest.TestCase):
    def test_upward_search_stops_at_dangling_config_marker(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            root = Path(project)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / "docengine.toml").symlink_to(Path(outside) / "missing.toml")
            with self.assertRaises(RootDiscoveryError):
                discover_roots(cwd=nested)

    def test_upward_search_stops_at_non_file_config_marker(self):
        with tempfile.TemporaryDirectory() as project:
            root = Path(project)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / "docengine.toml").mkdir()
            with self.assertRaises(RootDiscoveryError):
                discover_roots(cwd=nested)
