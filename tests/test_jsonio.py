import unittest

from docengine.jsonio import StrictJsonError, loads_strict


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected(self):
        with self.assertRaises(StrictJsonError):
            loads_strict('{"a": 1, "a": 2}')

    def test_nonstandard_numeric_constants_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(StrictJsonError):
                loads_strict('{"a": ' + value + '}')

class StrictJsonFiniteNumberTests(unittest.TestCase):
    def test_float_overflow_is_rejected(self):
        for payload in ("1e999", "-1e999", '{"value": 1e999}'):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(StrictJsonError, "finite runtime range"):
                    loads_strict(payload)
