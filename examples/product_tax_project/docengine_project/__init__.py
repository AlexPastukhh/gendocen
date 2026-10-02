"""Unrelated-domain fixture proving the builder core is generic."""


def register_builders(registry):
    from .builders import register
    register(registry)
