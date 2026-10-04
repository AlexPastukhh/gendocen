# Product + tax deterministic dependency fixture

This fixture is the runnable tutorial for **WF03/WF04** in `docs/CORE_WORKFLOWS.md`. It proves field-level tracked dependencies, mirrored target-oriented builder placement, selective invalidation and affected-only sync.

## Layout

```text
docs/catalog/price_with_tax.md
docs/_structured/catalog/price_with_tax.json
docengine_project/builders/catalog/price_with_tax.py
```

The same target path (`catalog/price_with_tax`) identifies the human view, descriptor and builder.

Builder registration is explicit:

```text
docengine_project/__init__.py
→ docengine_project/builders/__init__.py
→ builders/catalog/price_with_tax.py::register
```

A correctly placed `.py` file that is not imported/registered is not an active builder.

## Builder

The builder reads only:

```python
price = ctx.read("resource://catalog/product#/price")
tax_rate = ctx.read("resource://catalog/tax_policy#/rate")
```

Therefore the receipt contains field dependencies on `price` and `rate`. `product.unused_note` is deliberately present to prove that an unrelated field is not a dependency of `price_with_tax`.

## Safe runnable walkthrough

Copy the fixture before mutating it:

```bash
cp -R examples/product_tax_project /tmp/gendocen-product-tax
cd /tmp/gendocen-product-tax
```

Inspect ownership/resources:

```bash
docengine resources --json --project-root .
```

Check current dependency state:

```bash
docengine check --json --project-root .
```

### Consumed-field mutation

Change `docs/_structured/catalog/product.json` from `"price": 100` to `"price": 125`.

Run inspection only:

```bash
docengine check --json --project-root .
```

Expected: `resource://catalog/price_with_tax` becomes `build_required`; `docs/catalog/price_with_tax.md` is still the previous materialized view.

Repair only what is programmatically affected:

```bash
docengine sync --json --project-root .
```

Expected: the deterministic target rebuilds and affected Markdown is materialized with total `150.0`.

### Unrelated-field mutation

Now change only `product.unused_note`.

```bash
docengine check --json --project-root .
```

Expected: the field-level dependency for `price_with_tax` remains valid. The managed `product.md` view may require rematerialization because the product resource itself changed, but the derived price target does not need a dependency rebuild because it never read `unused_note`.

Run:

```bash
docengine sync --json --project-root .
docengine verify --json --project-root .
```

## Inspect captured evidence

```bash
docengine graph resource://catalog/price_with_tax --json --project-root .
docengine explain resource://catalog/price_with_tax --json --project-root .
```

The evidence should name the exact JSON Pointer fields.

## Do not do this

- Do not open the structured JSON directly inside the builder; use `ctx.read/get` for dependency-bearing inputs.
- Do not write `total` back into raw `product.json` or `tax_policy.json`.
- Do not calculate `total` inside the Markdown renderer.
- Do not edit generated `docs/catalog/price_with_tax.md` as canonical truth.
- Do not modify `src/docengine/**` for this project-specific formula.

## Code-change caveat

v0.1 computes a conservative package-wide project-code revision. Editing project Python can mark more deterministic builders `build_required` than the one module you touched. Data-field dependency evidence remains exact; code-revision invalidation is intentionally broader.
