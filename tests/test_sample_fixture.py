import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SampleFixtureTests(unittest.TestCase):
    def test_sample_project_fixture_exists(self):
        sample = ROOT / "examples/sample_project"
        self.assertTrue((sample / "docs").is_dir())
        self.assertTrue((sample / "docs/_structured").is_dir())
        self.assertTrue((sample / "docs/architecture/rationale.md").is_file())
