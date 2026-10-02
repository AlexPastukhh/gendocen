import tempfile
import unittest
from pathlib import Path

from docengine.config import ProjectConfigError, load_project_config


class ProjectConfigLayoutTests(unittest.TestCase):
    def _write(self, root: Path, structured: str, dependency: str) -> None:
        (root / "docengine.toml").write_text(
            "[docengine]\n"
            "config_version = 1\n"
            'documentation_root = "docs"\n'
            f'structured_dir = "{structured}"\n'
            f'dependency_dir = "{dependency}"\n',
            encoding="utf-8",
        )

    def test_structured_and_dependency_trees_must_be_disjoint(self):
        cases = [
            ("_same", "_same"),
            ("_meta", "_meta/dependency"),
            ("_meta/structured", "_meta"),
        ]
        for structured, dependency in cases:
            with self.subTest(structured=structured, dependency=dependency), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write(root, structured, dependency)
                with self.assertRaisesRegex(ProjectConfigError, "disjoint"):
                    load_project_config(root)

    def test_runtime_dirs_cannot_be_documentation_root_itself(self):
        for structured, dependency in ((".", "_dependency"), ("_structured", ".")):
            with self.subTest(structured=structured, dependency=dependency), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write(root, structured, dependency)
                with self.assertRaisesRegex(ProjectConfigError, "dedicated subdirectories"):
                    load_project_config(root)

    def test_config_paths_use_portable_forward_slashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root, r"_meta\\structured", "_dependency")
            with self.assertRaisesRegex(ProjectConfigError, "use '/' separators"):
                load_project_config(root)

    def test_schema_mapping_is_runtime_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docengine.toml").write_text(
                "[docengine]\nconfig_version=1\n"
                'documentation_root="docs"\nstructured_dir="_structured"\ndependency_dir="_dependency"\n'
                "[schemas]\n"
                '"example://schema/v1"="schema.json"\n',
                encoding="utf-8",
            )
            config = load_project_config(root)
            with self.assertRaises(TypeError):
                config.schemas["other"] = "other.json"  # type: ignore[index]
