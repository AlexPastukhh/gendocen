"""Target-oriented mirrored builder registry for the product/tax fixture."""

from .catalog.price_with_tax import register as register_price_with_tax


def register(registry):
    register_price_with_tax(registry)
