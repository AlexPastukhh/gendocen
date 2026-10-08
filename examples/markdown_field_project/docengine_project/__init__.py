"""Trusted project registration; all dependency-bearing reads are tracked."""
def register_builders(registry):
    from .field_plan import FIELDS
    from .builders import register
    FIELDS.register(registry)
    register(registry)

def register_semantic_dependencies(registry):
    from .dependency_rules import register
    register(registry)

def register_renderers(registry):
    from .renderers.guide import render
    registry.register("guide-markdown", render)
