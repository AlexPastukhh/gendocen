# Independent nested fields

This WF06 project uses the copyable helper in [`FIELD_DEPENDENCIES.md`](../../docs/FIELD_DEPENDENCIES.md). Inspect and trust its project Python before execution. Producers mirror their internal target modules under `builders/fields`; complete views mirror `builders/views`. `field_plan.py` binds canonical sources and declares providers. Registration imports final views lazily.

| Value | Formula / source |
|---|---|
| A.plan.deadline | inputs/B#/finish = 10 |
| C.rate | inputs/C#/rate = 5 |
| C.total | A.plan.deadline × C.rate = 50 |
| A.plan.budget | explicit raw override, otherwise C.total = 50 |
| A.plan | complete composition preserving its raw note/description |

A deadline request does not need the budget. Budget uses the deadline through C.total. Whole plan/root reads return complete objects; a whole-plan read from the budget producer would be a genuine cycle. `FIELDS.describe()` maps generated aggregate IDs to paths. Raw structures remain unchanged.

Copy outside the engine checkout first; the command prints `<root>`:

```bash
python -c "import shutil, tempfile; from pathlib import Path; p = Path(tempfile.mkdtemp()) / 'nested-project'; shutil.copytree('examples/nested_field_project', p); print(p)"
```

Install the bundled runtime following Quickstart, then:

```bash
docengine sync --project-root <root> --json
docengine graph --project-root <root> --json
docengine explain resource://views/A --project-root <root> --json
docengine verify --project-root <root> --json
```

The first sync creates fresh receipts and Markdown; no initial validated state is shipped. A.md contains deadline 10, budget 50, preserved prose and an explicit HTML anchor. Change calendar finish or C.rate and sync again. Add/remove `data.plan.budget` in canonical inputs/A to exercise nested override presence; null/false/zero/empty values count as supplied. A generated value in any other raw computed location is an ownership conflict.

The engine shares complete successful values/provenance within a stable CLI operation. Separate commands read current data/code. Changes observed during a command fail with a domain error; existing transaction rules preserve previous output/evidence. Default recursive execution remains in place.
