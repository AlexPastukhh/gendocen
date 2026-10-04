import copy
import json
import unittest
from pathlib import Path

from docengine.contracts import ContractError, load_json, validate_schema_instance

ROOT = Path(__file__).resolve().parents[1]


class SpecContractTests(unittest.TestCase):
    def test_registries_and_schemas_parse(self):
        for path in sorted((ROOT / "spec").rglob("*.json")):
            with self.subTest(path=str(path.relative_to(ROOT))):
                load_json(path)

    def test_use_case_registry_validates_against_schema(self):
        schema = load_json(ROOT / "spec/schemas/USE_CASE_REGISTRY.schema.json")
        registry = load_json(ROOT / "spec/registries/USE_CASE_REGISTRY.json")
        validate_schema_instance(registry, schema)

    def test_use_case_coverage_amendments_validate_against_schema(self):
        schema = load_json(ROOT / "spec/schemas/USE_CASE_COVERAGE_AMENDMENTS.schema.json")
        registry = load_json(ROOT / "spec/registries/USE_CASE_COVERAGE_AMENDMENTS.json")
        validate_schema_instance(registry, schema)

    def test_malformed_use_case_registry_fails(self):
        schema = load_json(ROOT / "spec/schemas/USE_CASE_REGISTRY.schema.json")
        registry = load_json(ROOT / "spec/registries/USE_CASE_REGISTRY.json")
        malformed = copy.deepcopy(registry)
        malformed["use_cases"][0].pop("id")
        with self.assertRaises(ContractError):
            validate_schema_instance(malformed, schema)

    def test_malformed_json_fails(self):
        path = ROOT / "tests/_malformed_contract_fixture.json"
        path.write_text('{"broken":', encoding="utf-8")
        try:
            with self.assertRaises(ContractError):
                load_json(path)
        finally:
            path.unlink(missing_ok=True)
