import contextlib
import io
import json
import tempfile
import unittest

from docengine.cli import COMMANDS, main
from docengine.versions import MACHINE_OUTPUT_SCHEMA_VERSION


class CliContractTests(unittest.TestCase):
    def _run(self, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(argv)
        return code, json.loads(stream.getvalue())

    def test_every_command_emits_same_json_envelope(self):
        required = {"schema_version", "command", "ok", "attention_required", "data", "warnings", "errors", "meta"}
        with tempfile.TemporaryDirectory() as project:
            for command in COMMANDS:
                with self.subTest(command=command):
                    code, payload = self._run([command, "--project-root", project, "--json"])
                    self.assertIn(code, {0, 2, 3, 4, 5})
                    self.assertEqual(set(payload), required)
                    self.assertEqual(payload["command"], command)
                    self.assertEqual(payload["schema_version"], MACHINE_OUTPUT_SCHEMA_VERSION)
                    self.assertEqual(payload["meta"]["exit_code"], code)
                    self.assertIn("engine_version", payload["meta"])
                    self.assertIn("status", payload["meta"])

    def test_json_usage_error_is_enveloped_and_exit_4(self):
        code, payload = self._run(["validate", "file://x.md", "--json"])
        self.assertEqual(code, 4)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["attention_required"])
        self.assertEqual(payload["meta"]["status"], "usage_error")
        self.assertEqual(payload["errors"][0]["code"], "usage_error")

    def test_unknown_command_with_json_is_enveloped_and_exit_4(self):
        code, payload = self._run(["not-a-command", "--json"])
        self.assertEqual(code, 4)
        self.assertEqual(payload["command"], "not-a-command")
        self.assertEqual(payload["meta"]["exit_code"], 4)
        self.assertTrue(payload["errors"])
