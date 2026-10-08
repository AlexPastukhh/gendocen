from ...field_plan import FIELDS

def build(ctx):
    return FIELDS.compose(ctx, "Guide")

def register(registry):
    registry.register("resource://views/guide", build)
