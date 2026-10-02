# Sample project

Показывает рекомендуемое размещение:

- human docs: `docs/...`
- managed structured sources: `docs/_structured/...` с зеркальной структурой
- runtime dependency state: `docs/_dependency/...`
- Markdown output path указан в `$docengine.materialize[].path` каждого managed JSON
- plain `architecture/rationale.md` не имеет JSON и всё равно может участвовать в whole-file/semantic dependency rules в project code.

- `_structured/architecture/system_summary.json` — descriptor fully-derived resource; output path lives in JSON, while builder logic would live in project code.

## P2 runtime fixture

The sample is executable by P1:

```bash
docengine resources --project-root . --json
```

`docengine.toml` registers two project schemas under `docengine_project/schemas/`. The third structured file is a `derived_descriptor`. Its builder lives in `docengine_project/builders.py`; P2 can build it in memory with tracked field dependencies. Persistent derived state/materialization execution arrive later.
