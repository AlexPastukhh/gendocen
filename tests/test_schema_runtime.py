import unittest

from docengine.schema import CoreSchemaValidator, SchemaValidationError


class RuntimeSchemaTests(unittest.TestCase):
    def test_supported_subset_validates_nested_data(self):
        schema = {
            "type": "object",
            "required": ["items"],
            "properties": {
                "items": {"type": "array", "minItems": 1, "items": {"type": "string"}}
            },
            "additionalProperties": False,
        }
        CoreSchemaValidator().validate({"items": ["a"]}, schema)
        with self.assertRaises(SchemaValidationError):
            CoreSchemaValidator().validate({"items": []}, schema)

    def test_unsupported_keyword_fails_instead_of_being_ignored(self):
        with self.assertRaisesRegex(SchemaValidationError, "unsupported JSON Schema keyword"):
            CoreSchemaValidator().validate("abc", {"type": "string", "pattern": "^a"})

    def test_malformed_schema_shape_fails(self):
        with self.assertRaisesRegex(SchemaValidationError, "required must be an array"):
            CoreSchemaValidator().validate({"a": 1}, {"type": "object", "required": "a"})
