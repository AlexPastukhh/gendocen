import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AuditHygieneTests(unittest.TestCase):
    def test_spec_audit_ignores_transient_python_and_pytest_artifacts(self):
        pytest_probe = ROOT / ".pytest_cache" / "docengine-audit-probe.txt"
        pycache_dir = ROOT / "tests" / "__pycache__"
        pyc_probe = pycache_dir / "docengine_audit_probe.pyc"
        pytest_probe.parent.mkdir(parents=True, exist_ok=True)
        pycache_dir.mkdir(parents=True, exist_ok=True)
        pytest_probe.write_text("transient", encoding="utf-8")
        pyc_probe.write_bytes(b"transient")
        try:
            proc = subprocess.run(
                [sys.executable, "tools/audit_spec.py"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("SPEC AUDIT OK", proc.stdout)
        finally:
            pytest_probe.unlink(missing_ok=True)
            pyc_probe.unlink(missing_ok=True)


    def test_spec_audit_ignores_git_internal_metadata(self):
        git_dir = ROOT / ".git"
        created_git_dir = not git_dir.exists()
        git_dir.mkdir(parents=True, exist_ok=True)
        probe = git_dir / "docengine-audit-probe"
        probe.write_text("transient git metadata", encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "tools/audit_spec.py"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("SPEC AUDIT OK", proc.stdout)
        finally:
            probe.unlink(missing_ok=True)
            if created_git_dir:
                try:
                    git_dir.rmdir()
                except OSError:
                    pass


class RepositoryPersistenceContractTests(unittest.TestCase):
    def test_repository_control_contract_is_present_and_dist_remains_tracked(self):
        required = [
            '.gitignore', '.gitattributes', '.editorconfig',
            '.github/workflows/ci.yml', '.github/workflows/release-gate.yml',
            'docs/REPOSITORY_WORKFLOW.md', 'plan/REPOSITORY_PERSISTENCE_AUDIT.md',
            'plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md',
        ]
        for rel in required:
            self.assertTrue((ROOT / rel).is_file(), rel)
        gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('__pycache__/', gitignore)
        self.assertIn('.pytest_cache/', gitignore)
        self.assertIn('build/', gitignore)
        self.assertIn('*.egg-info/', gitignore)
        active = {line.strip().rstrip('/') for line in gitignore.splitlines() if line.strip() and not line.strip().startswith('#')}
        self.assertNotIn('dist', active)

    def test_ci_and_release_workflows_cover_repository_gates(self):
        ci = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
        for command in (
            'python -m pytest -q',
            'python tools/audit_spec.py',
            'python tools/audit_axes.py --json',
            'python tools/release_manifest.py validate --json',
            'python tools/release_check.py --json',
        ):
            self.assertIn(command, ci)
        for token in ("'git'", "'status'", "'--porcelain'"):
            self.assertIn(token, ci)
        self.assertIn('windows-latest', ci)
        self.assertIn("'3.14'", ci)
        release = (ROOT / '.github/workflows/release-gate.yml').read_text(encoding='utf-8')
        self.assertIn('python tools/benchmark_release.py --json', release)
        self.assertIn('windows-portability', release)
        self.assertIn('windows-latest', release)
        self.assertIn("'3.14'", release)


class SourceCheckoutHarnessTests(unittest.TestCase):
    def test_source_checkout_pytest_path_is_declared(self):
        import tomllib
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["pytest"]["ini_options"]["pythonpath"], ["src"])
