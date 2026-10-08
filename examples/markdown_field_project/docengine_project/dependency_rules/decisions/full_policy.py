def register(registry):
    registry.register("file://decisions/full_policy.md", ["file://canonical/policy.md"],
                      rule_id="decisions.complete-policy")
