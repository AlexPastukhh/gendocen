"""Sample semantic dependency declarations."""


def register(registry):
    registry.register(
        "file://architecture/rationale.md",
        [("resource://policies/method_policy#/allowed_methods", "set")],
        rule_id="architecture.rationale-method-policy",
        dependency_type="semantic_review",
    )
