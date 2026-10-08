# Independent computed fields across documents

This runnable WF06 fixture uses the project helper described in [`docs/FIELD_DEPENDENCIES.md`](../../docs/FIELD_DEPENDENCIES.md). It starts with canonical raw JSON and derived descriptors; its first sync builds fresh receipts and Markdown. No prevalidated state is supplied.

## Field graph and source policy

| Field | Source or formula | Internal computed target |
|---|---|---|
| A.a | required inputs/A#/a = 11 | — |
| B.b1 | required inputs/B#/b1 = 7 | — |
| C.x | required inputs/C#/x = 10 | — |
| B.a1 | raw inputs/B#/a1 when present; otherwise C.x * 2 | fields/B_a1 |
| A.g | B.a1 | fields/A_g |
| B.g1 | A.g + 1 | fields/B_g1 |

Document A uses a field of B; document B uses a computed field of A. Their field graph is acyclic. Each independent computed field is a small whole internal resource wrapping `{"value": ...}`. Final views/A and views/B compose those values with raw inputs and materialize Markdown.

To model the simpler B.g1 dependency on raw A.a instead, change `builders/fields/B_g1.py` to return `fields.read(ctx, "A", "a")`. The same helper handles both declared source kinds.

## Layout and registration

```text
docengine_project/fields.py                 reusable project helper
docengine_project/field_plan.py             explicit provider/source map
docengine_project/builders/fields/B_a1.py    producer for internal fields/B_a1
docengine_project/builders/fields/A_g.py     producer for internal fields/A_g
docengine_project/builders/fields/B_g1.py    producer for internal fields/B_g1
docengine_project/builders/views/A.py        complete output builder
docengine_project/builders/views/B.py        complete output builder
docs/_structured/inputs/{A,B,C}.json         canonical inputs
docs/_structured/views/{A,B}.json            output descriptors
docs/views/{A,B}.md                         created by sync
```

Package `register_builders()` registers `FIELDS`, then both final builders. Internal resources need no descriptor JSON. Use tracked `FIELDS.read()` within producers; reading the final views as producer prerequisites would restore whole-document evaluation.

## Copy before mutating

From the engine checkout, copy this fixture outside the checkout. This portable command prints a new project path; use it as `<root>` in every command below:

```bash
python -c "import shutil, tempfile; from pathlib import Path; p = Path(tempfile.mkdtemp()) / 'field-project'; shutil.copytree('examples/field_dependency_project', p); print(p)"
```

If the CLI is not installed, follow the source/offline installation route in `CLEAN_CHAT_QUICKSTART.md` first. Inspect the copied package as trusted project code before executing it.

```bash
docengine resources --project-root <root> --json
docengine sync --project-root <root> --json
docengine graph --project-root <root> --json
docengine verify --project-root <root> --json
```

Expect A `{a: 11, g: 20}` and B `{b1: 7, a1: 20, g1: 21}` in generated views. `resources` inventories canonical documentation; the registered internal targets are visible through graph/receipts after sync.

## Change a computed prerequisite

In the copied `docs/_structured/inputs/C.json`, change `data.x` from 10 to 12.

```bash
docengine check --project-root <root> --json
docengine sync --project-root <root> --json
docengine verify --project-root <root> --json
```

Check reports build work and leaves the old Markdown intact. Sync produces A.g = B.a1 = 24, B.g1 = 25.

Change only C.unused_note and sync again: no deterministic target needs rebuilding because no producer reads that field.

## Switch between raw and computed B.a1

Add `"a1": 99` to raw B.data and run:

```bash
docengine sync --project-root <root> --json
docengine explain resource://fields/B_a1 --project-root <root> --json
docengine verify --project-root <root> --json
```

Expect A.g = B.a1 = 99, B.g1 = 100. B.a1's active source evidence includes the whole raw B used to test presence, with no C.x dependency. Change C.x to 13: outputs stay 99/100. Remove raw B.a1 and sync: current C.x is consumed again, producing 26/27.

The override is an intentional source policy, not an invitation to put generated values in raw data. Presence, including a present null, selects the raw value. Required inputs such as A.a never fall back to a guessed producer.

## Failure and ownership checks

- Missing A.a: required input error naming `resource://inputs/A#/a`.
- Undeclared logical field: provider error.
- Raw A.g or B.g1: source-conflict error; these fields have no raw override.
- A.g producer reads B.g1 while B.g1 reads A.g: true deterministic cycle reported through internal target names.

Correct canonical inputs/declarations/formulas, then sync and verify. Never edit generated Markdown or runtime receipts. Producers use JSON-compatible values and ordinary Python; do not add hidden file/network reads or private session access.

## Cache and scope

The dev23 CLI shares complete successful values/provenance across checks, rebuilding and materialization within one stable command. Separate commands evaluate current data/code again. Standalone BuildEngine calls use fresh sessions unless explicitly given a BuildOperation; the helper maintains no separate or persistent value cache.

This fixture declares literal top-level fields. The same helper supports independent nested output paths through `input_path`, `computed_path` and `read_path`, with canonical document bindings and intermediate composition. Details, conservative whole-object presence tracking, project-code invalidation and anchor presentation are in [`FIELD_DEPENDENCIES.md`](../../docs/FIELD_DEPENDENCIES.md).

## Nested counterpart and reuse

See [`nested_field_project`](../nested_field_project/README.md) for independent nested paths and intermediate composition. Legacy field labels in this fixture remain unchanged. The bundled dev23 CLI shares successful builds within each stable command; separate commands observe current data/code and do not share persistent values.
