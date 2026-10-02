import unittest

from docengine.output import CommandResult, Issue
from docengine.versions import ENGINE_VERSION, MACHINE_OUTPUT_SCHEMA_VERSION


class OutputEnvelopeTests(unittest.TestCase):
    def test_envelope_is_versioned_and_stable(self):
        payload = CommandResult(command="status", ok=True, status="ok", data={"x": 1}).to_dict(exit_code=0)
        self.assertEqual(
            set(payload),
            {"schema_version", "command", "ok", "attention_required", "data", "warnings", "errors", "meta"},
        )
        self.assertEqual(payload["schema_version"], MACHINE_OUTPUT_SCHEMA_VERSION)
        self.assertEqual(payload["meta"]["engine_version"], ENGINE_VERSION)
        self.assertEqual(payload["meta"]["status"], "ok")
        self.assertEqual(payload["meta"]["exit_code"], 0)
        self.assertEqual(payload["command"], "status")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["attention_required"])
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["errors"], [])

    def test_issues_are_split_into_warnings_and_errors(self):
        payload = CommandResult(
            command="verify",
            ok=False,
            status="verification_failed",
            issues=(
                Issue(code="warn", message="warning", severity="warning"),
                Issue(code="err", message="error", severity="error"),
            ),
            attention_required=True,
        ).to_dict(exit_code=3)
        self.assertEqual([x["code"] for x in payload["warnings"]], ["warn"])
        self.assertEqual([x["code"] for x in payload["errors"]], ["err"])
        self.assertEqual(payload["meta"]["exit_code"], 3)
