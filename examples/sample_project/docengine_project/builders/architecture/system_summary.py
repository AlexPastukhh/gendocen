"""Build docs/architecture/system_summary.md."""


def build_system_summary(ctx):
    title = ctx.read("resource://architecture/overview#/title")
    methods = ctx.read("resource://policies/method_policy#/allowed_methods")
    return {
        "title": "System Summary",
        "overview_title": title,
        "allowed_method_count": len(methods),
        "allowed_methods": list(methods),
    }


def register(registry):
    registry.register(
        "resource://architecture/system_summary",
        build_system_summary,
        builder_id="sample.build_system_summary",
        dependency_type="aggregate",
        comparator="exact",
    )
