"""Project-owned field producers; no engine-core extension is required."""


def register_builders(registry):
    from .field_plan import FIELDS
    from .builders import register

    FIELDS.register(registry)
    register(registry)
