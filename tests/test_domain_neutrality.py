import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("freelance", "opportunity", "payout", "researchhealth", "trendseries", "currentstatesnapshot")


class DomainNeutralityTests(unittest.TestCase):
    def test_core_package_has_no_first_consumer_domain_terms(self):
        for path in sorted((ROOT / "src/docengine").glob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for term in BANNED:
                with self.subTest(path=path.name, term=term):
                    self.assertNotIn(term, text)
