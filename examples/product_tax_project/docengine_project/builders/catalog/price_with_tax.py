"""Build docs/catalog/price_with_tax.md from exact structured fields."""


def build_price_with_tax(ctx):
    price = ctx.read("resource://catalog/product#/price")
    tax_rate = ctx.read("resource://catalog/tax_policy#/rate")
    return {"price": price, "tax_rate": tax_rate, "total": price * (1 + tax_rate)}


def register(registry):
    registry.register(
        "resource://catalog/price_with_tax",
        build_price_with_tax,
        builder_id="catalog.price_with_tax",
        dependency_type="compute",
        comparator="exact",
    )
