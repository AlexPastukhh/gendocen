"""Nested field project registration."""
def register_builders(registry):
    from .field_plan import FIELDS
    from .builders import register
    FIELDS.register(registry)
    register(registry)
