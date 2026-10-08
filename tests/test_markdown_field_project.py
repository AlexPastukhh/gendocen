"""The copyable Markdown route must work through the ordinary CLI lifecycle."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

FIXTURE = Path(__file__).resolve().parents[1] / "examples/markdown_field_project"


class MarkdownFieldProjectTests(unittest.TestCase):
    def test_executable_disposable_example(self):
        spec = importlib.util.spec_from_file_location("_markdown_example_check", FIXTURE / "check_example.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="gdm-") as temp:
            report = module.run_checks(Path(temp) / "project")
            self.assertTrue(report["ok"])
            self.assertTrue(all(scenario["ok"] for scenario in report["scenarios"]))


if __name__ == "__main__":
    unittest.main()
