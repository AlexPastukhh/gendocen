from ...field_plan import FIELDS

def build(ctx):
    return FIELDS.compose(ctx, "A")

def register(registry):
    registry.register("resource://views/A", build, builder_id="views.A")
