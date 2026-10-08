from ...field_plan import FIELDS


def build(ctx):
    return FIELDS.compose(ctx, "B", "resource://inputs/B")


def register(registry):
    registry.register("resource://views/B", build, builder_id="views.B")
