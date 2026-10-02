import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jsonschema

from docengine.cli import COMMANDS, build_parser, main

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "examples/product_tax_project"
SAMPLE = ROOT / "examples/sample_project"
CLI_SCHEMA = json.loads((ROOT / "spec/schemas/CLI_OUTPUT.schema.json").read_text(encoding="utf-8"))
VERIFY_SCHEMA = json.loads((ROOT / "spec/schemas/VERIFICATION_REPORT.schema.json").read_text(encoding="utf-8"))
CLI_REGISTRY = json.loads((ROOT / "spec/registries/CLI_COMMANDS.json").read_text(encoding="utf-8"))


def run_json(argv):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(argv)
    payload = json.loads(stream.getvalue())
    jsonschema.validate(payload, CLI_SCHEMA)
    return code, payload


def tree_snapshot(project: Path):
    result = {}
    for path in project.rglob("*"):
        if path.is_file():
            result[path.relative_to(project).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class P6ExitCodeAndEnvelopeTests(unittest.TestCase):
    def test_exit_code_classes_are_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            product = Path(tmp) / "product"
            shutil.copytree(PRODUCT, product)
            code, payload = run_json(["verify", "--project-root", str(product), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["attention_required"])

        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample"
            shutil.copytree(SAMPLE, sample)
            shutil.rmtree(sample / "docs/_dependency", ignore_errors=True)
            code, payload = run_json(["sync", "--all", "--project-root", str(sample), "--json"])
            self.assertEqual(code, 2)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["attention_required"])

        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample"
            shutil.copytree(SAMPLE, sample)
            shutil.rmtree(sample / "docs/_dependency", ignore_errors=True)
            code, payload = run_json(["verify", "--project-root", str(sample), "--json"])
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["attention_required"])

        code, payload = run_json(["validate", "file://x.md", "--json"])
        self.assertEqual(code, 4)
        self.assertEqual(payload["meta"]["status"], "usage_error")

        with mock.patch("docengine.cli._execute", side_effect=RuntimeError("boom")):
            code, payload = run_json(["status", "--json"])
        self.assertEqual(code, 5)
        self.assertEqual(payload["meta"]["status"], "internal_error")
        self.assertEqual(payload["errors"][0]["code"], "internal_error")

    def test_all_canonical_commands_are_present(self):
        self.assertEqual(
            set(COMMANDS),
            {"init", "status", "check", "diff", "explain", "sync", "rebuild", "validate", "materialize", "verify", "history", "graph", "recover", "migrate", "resources"},
        )



    def test_cli_registry_matches_parser_surface_and_exit_table(self):
        self.assertEqual(CLI_REGISTRY["commands"], list(COMMANDS))
        self.assertEqual(CLI_REGISTRY["machine_output_schema_version"], "2.0.0")
        self.assertEqual(CLI_REGISTRY["exit_codes"], {
            "0": "success with no blocking attention",
            "2": "command completed but review/attention remains",
            "3": "verification/domain validation failure",
            "4": "usage or project configuration error",
            "5": "internal/runtime failure",
        })
        parser = build_parser()
        subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        common = set(CLI_REGISTRY["common_options"])
        for command in COMMANDS:
            with self.subTest(command=command):
                sub = subparsers.choices[command]
                options = set()
                positional = []
                for action in sub._actions:
                    if action.dest == "help":
                        continue
                    if action.option_strings:
                        options.update(action.option_strings)
                    else:
                        positional.append((action.dest, action.nargs))
                specific = sorted(options - common - {"-h", "--help"})
                self.assertEqual(specific, sorted(CLI_REGISTRY["command_specs"][command]["options"]))
                target_contract = CLI_REGISTRY["command_specs"][command]["target"]
                if target_contract == "none":
                    self.assertFalse(any(dest == "target" for dest, _ in positional))
                else:
                    target = next((nargs for dest, nargs in positional if dest == "target"), None)
                    self.assertEqual(target, "?")

class P6VerifyTests(unittest.TestCase):
    def test_verify_allows_plain_markdown_project_without_project_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "docs").mkdir(parents=True)
            (project / "docs/readme.md").write_text("# docs\n", encoding="utf-8")
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(payload["data"]["report"]["ok"])
            self.assertFalse(any(x["code"] == "project_extension_invalid" for x in payload["data"]["report"]["findings"]))

    def test_verify_clean_project_passes_and_report_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            report = payload["data"]["report"]
            jsonschema.validate(report, VERIFY_SCHEMA)
            self.assertTrue(report["ok"])
            self.assertEqual(report["summary"]["blocking_findings"], 0)

    def test_verify_reports_multiple_blockers_and_does_not_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            before = tree_snapshot(project)
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            after = tree_snapshot(project)
            self.assertEqual(code, 3)
            self.assertEqual(before, after)
            report = payload["data"]["report"]
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("semantic_review_required", codes)
            self.assertIn("required_builder_unrecorded", codes)
            self.assertGreaterEqual(report["summary"]["blocking_findings"], 2)


    def test_verify_reports_renderer_component_failure_and_keeps_other_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                init.read_text(encoding="utf-8")
                + "\n\ndef register_renderers(registry):\n"
                  "    registry.register('markdown', lambda value, context: 'bad duplicate')\n",
                encoding="utf-8",
            )
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            report = payload["data"]["report"]
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("renderer_registry_invalid", codes)
            self.assertIn("dependency_integrity", report["sections"])
            self.assertIn("dependency_state", report["sections"])

    def test_verify_detects_generated_drift_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            generated = project / "docs/catalog/product.md"
            generated.write_text(generated.read_text(encoding="utf-8") + "\nmanual drift\n", encoding="utf-8")
            drifted = generated.read_bytes()
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertEqual(generated.read_bytes(), drifted)
            self.assertTrue(any(x["code"] == "materialization_not_current" for x in payload["data"]["report"]["findings"]))



    def test_verify_dependency_runtime_corruption_is_report_not_internal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            dependency = project / "docs/_dependency"
            real = project / "docs/dependency-real"
            dependency.rename(real)
            dependency.symlink_to(real.name, target_is_directory=True)
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            self.assertFalse(payload["ok"])
            report = payload["data"]["report"]
            jsonschema.validate(report, VERIFY_SCHEMA)
            self.assertTrue(any(f["code"] == "dependency_runtime_unavailable" for f in report["findings"]))
            self.assertEqual(report["sections"]["dependency_runtime"]["ok"], False)

    def test_nonexistent_or_file_project_root_is_usage_error_not_clean_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing"
            code, payload = run_json(["verify", "--project-root", str(missing), "--json"])
            self.assertEqual(code, 4)
            self.assertFalse(payload["ok"])
            file_root = root / "project-file"
            file_root.write_text("x", encoding="utf-8")
            code, payload = run_json(["verify", "--project-root", str(file_root), "--json"])
            self.assertEqual(code, 4)
            self.assertFalse(payload["ok"])

    def test_verify_classifies_missing_semantic_rule_as_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)
            code, synced = run_json(["sync", "--all", "--project-root", str(project), "--json"])
            self.assertEqual(code, 2)
            target = "file://architecture/rationale.md"
            code, packet = run_json(["explain", target, "--project-root", str(project), "--json"])
            context = packet["data"]["review_context_id"]
            code, _ = run_json([
                "validate", target, "--result", "still-valid", "--reason", "probe",
                "--review-context", context, "--project-root", str(project), "--json",
            ])
            self.assertEqual(code, 0)
            code, _ = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            (project / "docengine_project/__init__.py").write_text(
                'def register_builders(registry):\n'
                '    from .builders import register\n'
                '    register(registry)\n',
                encoding="utf-8",
            )
            code, payload = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            row = next(x for x in payload["data"]["report"]["sections"]["current_checks"] if x["target"] == target)
            self.assertEqual(row["status"], "invalid")
            self.assertIn("semantic_rule_unavailable", row["reason_codes"])

class P6ReadOnlyBoundaryTests(unittest.TestCase):
    def test_all_read_only_commands_preserve_project_file_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            for cache in list(project.rglob("__pycache__")):
                shutil.rmtree(cache)
            target = "resource://catalog/price_with_tax"
            commands = [
                ["status"],
                ["diff", target],
                ["explain", target],
                ["history", target],
                ["graph", target],
                ["resources"],
                ["verify"],
            ]
            before = tree_snapshot(project)
            for argv in commands:
                with self.subTest(argv=argv):
                    code, payload = run_json([*argv, "--project-root", str(project), "--json"])
                    self.assertIn(code, {0, 2, 3})
                    self.assertIn("meta", payload)
                    self.assertEqual(tree_snapshot(project), before)


class P6ProtocolBoundaryRegressionTests(unittest.TestCase):
    def _run_subprocess(self, project: Path, argv):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [os.environ.get("PYTHON", "python"), "-m", "docengine.cli", *argv, "--project-root", str(project), "--json"],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )

    def test_project_import_system_exit_stays_inside_json_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            (project / "docengine_project/__init__.py").write_text('raise SystemExit("project-exit-probe")\n', encoding="utf-8")
            for command in (["verify"], ["check"], ["sync"]):
                with self.subTest(command=command):
                    proc = self._run_subprocess(project, command)
                    self.assertIn(proc.returncode, {3, 4, 5})
                    self.assertEqual(proc.stderr, "")
                    payload = json.loads(proc.stdout)
                    jsonschema.validate(payload, CLI_SCHEMA)

    def test_builder_system_exit_stays_inside_json_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            (project / "docengine_project/__init__.py").write_text(
                'def register_builders(registry):\n'
                '    def b(ctx):\n'
                '        raise SystemExit("builder-exit-probe")\n'
                '    registry.register("resource://catalog/price_with_tax", b)\n',
                encoding="utf-8",
            )
            for command in (["rebuild", "resource://catalog/price_with_tax"], ["verify"]):
                with self.subTest(command=command):
                    proc = self._run_subprocess(project, command)
                    self.assertEqual(proc.returncode, 3)
                    self.assertEqual(proc.stderr, "")
                    payload = json.loads(proc.stdout)
                    jsonschema.validate(payload, CLI_SCHEMA)

    def test_registration_and_renderer_system_exit_stay_inside_json_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                'def register_builders(registry):\n'
                '    raise SystemExit("register-exit-probe")\n',
                encoding="utf-8",
            )
            proc = self._run_subprocess(project, ["check"])
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(proc.stderr, "")
            jsonschema.validate(json.loads(proc.stdout), CLI_SCHEMA)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            init = project / "docengine_project/__init__.py"
            init.write_text(
                'from . import builders as _builders\n'
                'def register_builders(registry):\n'
                '    _builders.register(registry)\n'
                'def register_renderers(registry):\n'
                '    def render(value, context):\n'
                '        raise SystemExit("renderer-exit-probe")\n'
                '    registry.register("markdown", render, replace=True)\n',
                encoding="utf-8",
            )
            proc = self._run_subprocess(project, ["materialize", "--all"])
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(proc.stderr, "")
            jsonschema.validate(json.loads(proc.stdout), CLI_SCHEMA)

    def test_human_status_failure_retains_invalid_target_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            state_path = project / "docs/_dependency/state/dependency_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            target = next(iter(state["targets"]))
            state["targets"][target]["status"] = "invalid"
            state["targets"][target]["reason_codes"] = ["probe_invalid"]
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            code, payload = run_json(["status", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                human_code = main(["status", "--project-root", str(project)])
            self.assertEqual(human_code, code)
            text = stream.getvalue()
            self.assertIn("invalid=1", text)
            self.assertIn(target, text)
            self.assertEqual(payload["data"]["targets"][target]["status"], "invalid")

    def test_human_verify_usage_error_includes_issue_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(["verify", "--project-root", str(missing)])
            self.assertEqual(code, 4)
            self.assertIn("project root does not exist", stream.getvalue())


class P6AgentWorkflowTests(unittest.TestCase):
    def test_fresh_ai_cli_only_workflow_reaches_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(SAMPLE, project)
            shutil.rmtree(project / "docs/_dependency", ignore_errors=True)

            code, synced = run_json(["sync", "--all", "--project-root", str(project), "--json"])
            self.assertEqual(code, 2)
            self.assertTrue(synced["attention_required"])

            target = "file://architecture/rationale.md"
            code, packet = run_json(["explain", target, "--project-root", str(project), "--json"])
            self.assertEqual(code, 2)
            context = packet["data"]["review_context_id"]

            code, accepted = run_json([
                "validate", target,
                "--result", "still-valid",
                "--reason", "P6 fresh-agent review",
                "--review-context", context,
                "--actor-kind", "ai",
                "--project-root", str(project),
                "--json",
            ])
            self.assertEqual(code, 0)
            self.assertTrue(accepted["ok"])

            code, synced_again = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertFalse(synced_again["attention_required"])

            code, verified = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            self.assertTrue(verified["data"]["report"]["ok"])

    def test_human_and_json_status_share_same_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(PRODUCT, project)
            code, payload = run_json(["status", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0)
            counts = payload["data"]["counts"]
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                human_code = main(["status", "--project-root", str(project)])
            self.assertEqual(human_code, code)
            text = stream.getvalue()
            for key, value in counts.items():
                self.assertIn(f"{key}={value}", text)
