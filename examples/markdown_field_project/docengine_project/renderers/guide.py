def render(value, context):
    return ("# " + value["title"] + "\n\n"
        + "> Semantic Owner Dependency\n"
        + "> - `REPRESENTS` [Canonical reuse policy](../canonical/policy.md#reuse-policy) — `DEMO.REUSE-POLICY`.\n\n"
        + "Generated quotation; the linked source remains authoritative.\n\n"
        + value["note"] + "\n\n"
        + value["sections"]["reuse"]["text"])
