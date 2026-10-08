from ...field_plan import FIELDS

def build(ctx):
    return FIELDS.compose(ctx, "C")

def register(registry):
    registry.register("resource://views/C", build, builder_id="views.C")
