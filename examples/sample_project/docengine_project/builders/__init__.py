"""Target-oriented mirrored builder registry for the sample project."""

from .architecture.system_summary import register as register_system_summary


def register(registry):
    register_system_summary(registry)
