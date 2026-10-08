import pytest
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from docengine.cli import main
from docengine.project import ProjectInitializationError, initialize_project


class P1InitTests(unittest.TestCase):
    def test_init_is_idempotent_and_does_not_promote_plain_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            docs = project / "docs"
            docs.mkdir()
            readme = docs / "README.md"
            readme.write_text("# Plain\n", encoding="utf-8")
            before = readme.read_bytes()

            first = initialize_project(project_root=project)
            second = initialize_project(project_root=project)
            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertEqual(readme.read_bytes(), before)
            self.assertFalse((docs / "_structured/README.json").exists())
            self.assertTrue((project / "docengine.toml").is_file())
            self.assertTrue((docs / "_dependency/state").is_dir())

    def test_cli_init_returns_machine_readable_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["init", "--project-root", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(stream.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["meta"]["status"], "initialized")

    def test_cli_init_rejects_empty_docs_root_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["init", "--project-root", str(project), "--docs-root", "", "--json"])
            payload = json.loads(stream.getvalue())
            after = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
            self.assertEqual(code, 4, payload)
            self.assertFalse(payload["ok"])
            self.assertIn("documentation root must not be empty", json.dumps(payload))
            self.assertEqual(after, before)

    def test_init_rejects_docs_outside_project(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ProjectInitializationError):
                initialize_project(project_root=project, docs_root=outside)

class P1InitSymlinkSafetyTests(unittest.TestCase):
    @pytest.mark.requires_symlink
    def test_existing_docs_symlink_outside_is_rejected_before_runtime_writes(self):
        with tempfile.TemporaryDirectory() as project_tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(project_tmp)
            outside = Path(outside_tmp)
            (project / "docengine.toml").write_text(
                '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\nstructured_dir = "_structured"\ndependency_dir = "_dependency"\n',
                encoding="utf-8",
            )
            (project / "docs").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ProjectInitializationError):
                initialize_project(project_root=project)
            self.assertEqual(list(outside.iterdir()), [])

class P1InitConfigSymlinkSafetyTests(unittest.TestCase):
    @pytest.mark.requires_symlink
    def test_dangling_config_symlink_is_rejected_without_writing_target(self):
        with tempfile.TemporaryDirectory() as project_tmp, tempfile.TemporaryDirectory() as outside_tmp:
            project = Path(project_tmp)
            outside_target = Path(outside_tmp) / "would_be_written.toml"
            (project / "docengine.toml").symlink_to(outside_target)
            with self.assertRaisesRegex(ProjectInitializationError, "symlinks are not allowed"):
                initialize_project(project_root=project)
            self.assertFalse(outside_target.exists())
