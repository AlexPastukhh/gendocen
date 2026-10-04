"""Target-oriented mirrored semantic dependency registry."""

from .architecture.rationale import register as register_architecture_rationale


def register(registry):
    register_architecture_rationale(registry)
