# Sample project — structured, derived and semantic workflows

This fixture demonstrates the recommended v0.1 ownership/layout model and the semantic-review workflow from **WF05**.

## Layout

```text
docs/
  architecture/
    overview.md
    rationale.md
    system_summary.md
  policies/
    method_policy.md
  _structured/
    architecture/
      overview.json
      system_summary.json
    policies/
      method_policy.json

docengine_project/
  builders/
    architecture/
      system_summary.py
  dependency_rules/
    architecture/
      rationale.py
```

Structured sources mirror their generated documentation targets. Project executable semantics live outside `docs/` but mirror the produced/semantic target path for discoverability.

Historical `docengine_project/builders.py` and `semantic_rules.py` files are retained only because accepted phase evidence names those paths. They are pure forwarding registration indexes; active builder/rule semantics live in the mirrored packages.

## Safe runnable setup

Work on a disposable copy **before running any project command**:

```bash
cp -R examples/sample_project /tmp/gendocen-sample
cd /tmp/gendocen-sample
```

All commands below assume that copied fixture is the current directory and therefore use `--project-root .`.

## Ownership discovery

Before changing a visible Markdown file, start with:

```bash
docengine resources --json --project-root .
```

- `architecture/overview.md` and `policies/method_policy.md` are generated managed views; change their structured JSON.
- `architecture/system_summary.md` is fully derived; change its upstream data or mirrored builder.
- `architecture/rationale.md` is reported as plain. For a plain file, check semantic ownership too:

```bash
docengine graph file://architecture/rationale.md --json --project-root .
```

Its non-empty `rules`/`rule_edges` identify the semantic dependency. The Markdown itself remains canonical prose, and its authoritative rule lives at `docengine_project/dependency_rules/architecture/rationale.py`.

## Deterministic derived target

`system_summary.json` is a `derived_descriptor`. Its active mirrored builder is:

```text
docengine_project/builders/architecture/system_summary.py
```

and is registered through:

```text
docengine_project/__init__.py
→ builders/__init__.py
→ architecture/system_summary.py::register
```

The builder uses tracked field reads and creates a transient `DerivedObject`; persistent dependency evidence lives under `docs/_dependency`.

## Semantic review walkthrough

Continue in the copied fixture established above. The bundled sample intentionally starts with an **unvalidated** semantic rule, so first establish a validated baseline. Run:

```bash
docengine sync --json --project-root .
docengine explain file://architecture/rationale.md --json --project-root .
```

The first semantic attention is `initial_validation_required`. Copy the returned `review_context_id` and accept the current rationale explicitly:

```bash
docengine validate file://architecture/rationale.md \
  --project-root . \
  --result still-valid \
  --reason "Initial sample baseline is accepted." \
  --review-context REVIEW_CONTEXT_ID \
  --json
```

Now change `docs/_structured/policies/method_policy.json` so `allowed_methods` differs from that validated baseline, then run:

```bash
docengine sync --json --project-root .
```

Deterministic work may rebuild automatically. `file://architecture/rationale.md` must become semantic attention (`review_required`) because the **validated dependency changed**, while the engine leaves the prose untouched.

Inspect review evidence:

```bash
docengine explain file://architecture/rationale.md --json --project-root .
docengine diff file://architecture/rationale.md --json --project-root .
```

The reason/diff should now reflect a dependency/rule-context change rather than only `initial_validation_required`. If the existing rationale is still semantically valid, record another explicit `still-valid` decision with the new review context. If it needs editing, change the canonical Markdown, refresh `explain`, and validate with `--result updated`.

Finish with:

```bash
docengine sync --json --project-root .
docengine verify --json --project-root .
```

## Trust boundary

Project extension code is trusted Python. `verify` is read-only for engine-managed state but can execute project callbacks; it is not a security sandbox for arbitrary side effects.
