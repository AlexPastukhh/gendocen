# Clean-Chat Quickstart

Use this page when a new human/AI session receives a gendocen repository or project **without prior conversation context**. It is intentionally short: establish the safe operating context, route the task to one workflow, then read deeper reference material only as needed.

## 1. Decide which kind of work you are doing

There are two different starts:

### A. Project authoring / using gendocen

You are changing a documentation project that uses gendocen: structured data, builders, dependency rules, generated views, semantic review, or project state.

Continue with this quickstart and then route to `CORE_WORKFLOWS.md`.

### B. Maintaining the gendocen engine itself

You are changing `src/docengine/**`, release tooling, runtime contracts, packaging, CI, or accepted engine evidence.

Stop this project-authoring quickstart and use:

1. `START_HERE_AGENT.md`
2. `OPEN_QUESTIONS_AND_AMBIGUITIES.md`
3. `docs/REPOSITORY_WORKFLOW.md`
4. `docs/RELEASE_GATE.md`

Do not edit engine core merely because one documentation project needs a new dependency.

## 2. Environment preflight

The runtime requires Python 3.11+.

Check the environment before changing a project:

```bash
python --version
docengine --version
```

If `docengine` is not installed and you are working from a gendocen source checkout with package-index access:

```bash
python -m pip install -e .
```

If package-index access is unavailable and the release archive contains the bundled wheel, ordinary project use can bootstrap offline without invoking the source build backend:

```bash
python -m pip install --no-index dist/generic_documentation_engine-0.1.0.dev22-py3-none-any.whl
docengine --version
```

For engine development/tests rather than ordinary project use:

```bash
python -m pip install -e '.[test]'
```

Editable source/test installation may require package-index access because the repository does not vendor its build/test dependencies. The bundled wheel is an offline fallback for using the released runtime; it is not a replacement for an editable development environment.

## 3. Find the intended project root before running project commands

A normal gendocen project has `docengine.toml` in its project root.

Project-root discovery precedence is:

1. explicit `--project-root`;
2. upward search for `docengine.toml` from the current working directory;
3. current directory when no marker exists.

`--docs-root` does **not** select a project. It overrides the documentation root *inside the already selected project root* and remains confined to that project.

Explicit `--project-root` and explicit `--docs-root` values must both be non-empty. An empty shell variable is rejected instead of falling back to cwd/project-root semantics. `--docs-root` remains an optional override inside the already selected project; omit the option when you want the configured/default documentation root.

For an unfamiliar repository, prefer an **explicit project root** until you understand the tree:

```bash
docengine resources --project-root /path/to/project --json
```

Do not assume the gendocen engine source checkout itself is the documentation project you intend to mutate. If no `docengine.toml` exists because you are intentionally creating a new project, initialize the intended root explicitly so an ancestor marker cannot capture the command:

```bash
docengine init --project-root /path/to/intended/project --json
```

## 4. Trust preflight before importing project Python

`docengine_project/**` is ordinary trusted/cooperative Python, not a sandbox. Importing project extensions can execute Python import-time code, and callbacks can perform arbitrary filesystem/network/process side effects.

In an unfamiliar project:

1. Read `docengine.toml` and identify `project_package` (default `docengine_project`).
2. Inspect that package before executing commands that load project extensions.
3. Establish that the code is trusted for the current task/environment.

In v0.1, commands such as `check`, `diff`, `explain`, `graph`, `validate`, `rebuild`, `materialize`, `sync`, and `verify` can load project extension code. `verify` is read-only with respect to engine-managed state, but it is **not** a security sandbox for project callbacks.

`resources` is suitable for initial resource inventory/ownership discovery because the v0.1 `resources` command scans the resource catalog without loading the project extension package. It is **not** proof that a builder is registered.

## 5. Determine ownership before editing visible Markdown

Start with:

```bash
docengine resources --project-root /path/to/project --json
```

For managed/derived generated output, follow the mirrored source/code rather than editing the visible Markdown.

If the resource is plain Markdown and project code has passed the trust preflight, inspect semantic ownership with:

```bash
docengine graph file://path/to/file.md --project-root /path/to/project --json
```

Use this classification:

```text
managed/generated  -> edit docs/_structured/<path>.json
derived/generated  -> edit upstream structured inputs and/or mirrored builder
plain + semantic rule -> Markdown is canonical; inspect mirrored dependency rule/review state
plain + no semantic rule -> ordinary canonical Markdown
```

Normal mirrored authoring layout:

```text
docs/<logical/path>.md
docs/_structured/<logical/path>.json
docengine_project/builders/<logical/path>.py
docengine_project/dependency_rules/<logical/path>.py
```

A mirrored Python file is not active until the project registration surface imports/registers it.

## 6. Route the task instead of reading the whole manual

| Goal | Read next |
|---|---|
| Keep existing Markdown plain / adopt gendocen incrementally | `CORE_WORKFLOWS.md` → WF01 |
| Make selected information structured/addressable | WF02 |
| Create a deterministic derived document/dependency | WF03 |
| Inputs changed; selectively recompute deterministic outputs | WF04 |
| Semantic assumptions changed; review prose/policy | WF05 |
| Build a derived target from another derived target | WF06 |
| Aggregate many resources with changing membership | WF07 |
| Produce Markdown/JSON/HTML or integrate with an application | WF08 |
| Understand why a target is affected/stale | WF09 |
| Regenerate/verify reproducibility and drift | WF10 |
| Recover an interrupted mutation | WF11 |
| Migrate persisted runtime layout | WF12 |
| Promote/demote plain vs managed docs | Future only: FWF01/FWF02; no v0.1 command |

Atomic normative behavior is in `USE_CASES.md`; use it when a workflow points to a `DOCxx` contract or when exact command semantics matter.

## 7. Default project-authoring loop

After ownership/trust are established and the task-specific workflow is understood:

```text
EDIT canonical project data / mirrored project code
  ↓
docengine sync --project-root <root> --json
  ├─ deterministic missing/build_required targets -> selective rebuild
  ├─ affected generated outputs -> materialize
  └─ semantic review_required/stale -> attention only
  ↓
for semantic attention:
  explain/diff -> human/AI judgment -> validate still-valid|updated
  ↓
docengine sync --project-root <root> --json
  ↓
docengine verify --project-root <root> --json
```

Use the same explicit project root when you deliberately want to inspect dependency changes before deterministic rebuild:

```bash
docengine check --project-root <root> --json
```

Likewise, full materialization selection keeps the explicit root:

```bash
docengine sync --project-root <root> --all --json
```

`sync --all` broadens materialization; it does not force-rebuild all valid builders.

## 8. Before saying the task is finished

For dependency-authoring work, confirm all of the following:

- you edited the canonical owner, not a generated view;
- project-specific logic lives in `docengine_project/**`, not `src/docengine/**`;
- dependency-bearing builder inputs use `ctx.read()` / `ctx.get()`;
- the mirrored builder/rule is actually registered;
- `sync` reaches the expected deterministic/semantic state;
- `graph`/`explain` show the expected dependency evidence;
- `verify` reports the expected final project state;
- you did not treat trusted project Python as sandboxed.

Then continue with the relevant `CORE_WORKFLOWS.md` section for task-specific details.
