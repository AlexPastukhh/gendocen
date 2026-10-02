"""Project-owned builders for the sample documentation project."""


def register_builders(registry):
    from .builders import register
    register(registry)


def register_semantic_dependencies(registry):
    from .semantic_rules import register
    register(registry)
