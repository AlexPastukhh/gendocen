"""Semantic review dependency for docs/architecture/rationale.md.

This mirrored module is the authoritative project-owned definition of the rule.
"""


def register(registry):
    registry.register(
        "file://architecture/rationale.md",
        [("resource://policies/method_policy#/allowed_methods", "set")],
        rule_id="architecture.rationale-method-policy",
        dependency_type="semantic_review",
    )
