import unittest

from docengine.refs import RefError, ResourceRef


class ResourceRefTests(unittest.TestCase):
    def test_resource_round_trip_with_pointer_escaping(self):
        ref = ResourceRef.parse("resource://policies/method_policy#/a~1b/~0value/0")
        self.assertEqual(ref.logical_resource_id, "policies.method_policy")
        self.assertEqual(ref.pointer_parts, ("a/b", "~value", "0"))
        self.assertEqual(ResourceRef.parse(str(ref)), ref)

    def test_from_resource_id_is_canonical(self):
        ref = ResourceRef.from_resource_id("architecture.overview", "/summary")
        self.assertEqual(str(ref), "resource://architecture/overview#/summary")

    def test_file_ref_round_trip(self):
        ref = ResourceRef.parse("file://architecture/rationale.md")
        self.assertEqual(ref.file_path, "architecture/rationale.md")
        self.assertEqual(ResourceRef.parse(str(ref)), ref)


    def test_invalid_managed_resource_ids_fail(self):
        for value in ("single", ".id", "ns.", "ns.id/other", "na me.id"):
            with self.subTest(value=value), self.assertRaises(RefError):
                ResourceRef.from_resource_id(value)

    def test_malformed_refs_fail_clearly(self):
        bad = [
            "resource://missing-id",
            "resource:///id",
            "resource://ns/a/b",
            "resource://ns/id#not-a-pointer",
            "resource://n%2Fs/id",
            "resource://ns/i%2Fd",
            "resource://ns/id%20space",
            "file://../escape.md",
            "file://architecture/./rationale.md",
            "file://architecture/rationale.md#/section",
            "https://example.com/x",
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(RefError):
                ResourceRef.parse(value)

class ResourceRefCanonicalityTests(unittest.TestCase):
    def test_direct_construction_cannot_bypass_resource_identity_validation(self):
        with self.assertRaises(RefError):
            ResourceRef(scheme="resource", namespace="bad/name", resource_id="x")
        with self.assertRaises(RefError):
            ResourceRef(scheme="file", file_path="../escape.md")

    def test_noncanonical_percent_encoding_is_rejected_instead_of_normalized(self):
        for value in (
            "resource://foo/%62ar",
            "resource://f%6Fo/bar",
            "file://architecture/%72ationale.md",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(RefError, "already be canonical"):
                ResourceRef.parse(value)
