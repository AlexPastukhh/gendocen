# AI / CI Usage Protocol — v0.1

This protocol is the normal machine-operating surface for an AI/CI consumer. A zero-context session should read `CLEAN_CHAT_QUICKSTART.md` first, then the relevant section of `CORE_WORKFLOWS.md`. Atomic behavioral contracts live in `USE_CASES.md`.

## 1. Learn the engine before mutating a project

Fresh agent reading order:

1. `README.md`
2. `docs/CLEAN_CHAT_QUICKSTART.md`
3. the task-specific section of `docs/CORE_WORKFLOWS.md`
4. `docs/USE_CASES.md` when exact atomic behavior is needed
5. relevant reference docs only as needed (`ARCHITECTURE`, `PRINCIPLES`, `CODE_MODEL`, `DEPENDENCY_MODEL`, `MATERIALIZATION_RUNTIME`, `HARDENING_RUNTIME`)

`START_HERE_AGENT.md` is the maintainer/release handoff route, not the primary product tutorial.


## 1A. Zero-context environment / root / trust preflight

Before a fresh session mutates an unfamiliar project:

1. confirm Python 3.11+ and `docengine --version`;
2. locate the intended `docengine.toml` or pass an explicit `--project-root`;
3. inspect `docengine.toml` and its configured `project_package`;
4. inspect unfamiliar `docengine_project/**` before commands that load project extensions;
5. use `resources --project-root ... --json` for initial inventory, not as builder-registration proof.

The full decision path and task router live in `CLEAN_CHAT_QUICKSTART.md`.

## 2. Machine contract

Every `--json` response uses schema 2.0.0 top-level fields:

```text
schema_version
command
ok
attention_required
data
warnings
errors
meta
```

Exit policy:

```text
0 success / no blocking attention
2 completed with attention/review remaining
3 domain/verification failure
4 usage/project configuration error
5 internal/runtime failure
```

Exit `2` is an expected operating state. Inspect the JSON payload rather than treating every nonzero exit as a crash.

## 3. Project-authoring edit boundary

Normal AI project edits belong in:

```text
docs/_structured/**
docengine_project/**
plain canonical docs/**/*.md only after ownership classification
```

Do not edit `docs/_dependency/**` directly. Do not edit `src/docengine/**` merely to create one project's dependency.

Accepted target-oriented mirroring:

```text
docs/<logical/path>.md
docs/_structured/<logical/path>.json
docengine_project/builders/<logical/path>.py
docengine_project/dependency_rules/<logical/path>.py
```

A mirrored module must also be imported/registered through `docengine_project.register_builders(...)` or `register_semantic_dependencies(...)`.

## 4. Before editing visible Markdown: determine ownership

Run:

```bash
docengine resources --json --project-root <root>
```

Use `resources` to identify managed/derived generated ownership. If the file is reported as plain, make one more check before editing it:

```bash
docengine graph file://PATH --json --project-root <root>
```

- managed/generated Markdown → edit mirrored structured source;
- fully-derived/generated target → edit upstream structured source or mirrored builder;
- plain target with non-empty `rules`/`rule_edges` → Markdown remains canonical semantic prose, but inspect its mirrored semantic rule and review state;
- plain target with no semantic rule → ordinary canonical Markdown.

Do not infer ownership from `.md` extension alone, and do not infer semantic-rule membership from `resources` alone.

## 5. Default edit/sync/review/verify loop

After changing structured data or project code, normally run:

```bash
docengine sync --json --project-root <root>
```

`sync` performs dependency checking first. It selectively rebuilds deterministic targets that lack an active receipt or are `build_required`, materializes affected outputs, and leaves semantic `review_required`/`stale` targets as attention.

If you want inspection before any rebuild, run:

```bash
docengine check --json --project-root <root>
```

`check` may persist dependency state/events and execute builders in memory to resolve current derived sources. Recording replacement deterministic build receipts and writing generated content belong to rebuild/sync/materialization. An empty `sync.data.rebuilt` list reports no evidence-advancing rebuilds; it does not prove that no source builder was evaluated during checking.

For every semantic attention target:

```bash
docengine explain TARGET --json --project-root <root>
docengine diff TARGET --json --project-root <root>
```

Review externally. If content still holds:

```bash
docengine validate TARGET \
  --project-root <root> \
  --result still-valid \
  --reason "..." \
  --review-context reviewctx-... \
  --actor-kind ai \
  --json
```

If content needs change, edit the canonical semantic target, refresh `explain`, then validate with `--result updated`.

Finish with:

```bash
docengine sync --json --project-root <root>
docengine verify --json --project-root <root>
```

## 6. `sync --all` is not force-rebuild-all

```bash
docengine sync --all --json --project-root <root>
```

keeps deterministic rebuild selection evidence-driven. `--all` broadens materialization to all registered views. Do not use it to mean “ignore valid receipts and recompute every builder.”

## 7. Correct dependency authoring

Dependency-bearing values inside deterministic builders must come through tracked APIs:

```python
price = ctx.read("resource://catalog/product#/price")  # field dependency
product = ctx.get("resource://catalog/product")        # whole-resource dependency
```

Do not hide dependency-bearing reads behind direct `open()`, `Path.read_text()`, network/database calls, or arbitrary helper I/O. Such reads are not automatically represented in the receipt.

Do not copy computed values into raw canonical JSON merely to avoid writing a builder. Do not calculate dependency-derived values inside renderers. See WF03 in `CORE_WORKFLOWS.md`.

When creating/changing a formula, source map or dependent assertion, use the applicable [Dependency Authoring Checks](DEPENDENCY_AUTHORING_CHECKS.md). In particular, the selected source must supply every used value/contract: if A uses a period owned by C, a dependency only on B's prose "consult C" does not capture that period. Read/depend on C's exact field, or on a tracked derived B field that actually exposes it. A structurally valid receipt does not establish completeness of undeclared assumptions. These checks apply when authoring/changing the connection; ordinary source edits use the normal sync loop without a repeated full manual catalogue review.

When documents refer to independently computed fields in both directions, route to WF06 and [`FIELD_DEPENDENCIES.md`](FIELD_DEPENDENCIES.md). Reuse the project `FieldPlan` helper, declare one provider per field, and resolve computed prerequisites through internal field resources rather than final whole-document views. Missing required inputs are errors; raw-first behavior requires an explicit override and producer. Register the plan plus final builders, test source switching, inspect graph/explain and finish with verify. This authoring route does not require engine-core edits or direct runtime-state changes.

## 8. Registration and discoverability

Creating a Python file is not enough. A builder/rule becomes active only through the project registration surface. `resources` is useful for inventory/ownership but is **not** proof that a derived builder is registered. After authoring new mirrored code, confirm registration with `sync`/`rebuild`, or use `graph` and require `runtime_diagnostics` to be empty; resolve any `no registered builder`/project-extension diagnostic before considering the dependency complete.

## 9. Semantic authority

Never infer `still-valid` or `updated` automatically from a structural diff. The engine proves that validated context changed; human/AI judgment chooses the semantic outcome and records reason/context/evidence.

## 10. Generated views

Normal full file regeneration:

```bash
docengine materialize --all --json --project-root <root>
```

A deliberate orphan ownership transition is explicit:

```bash
docengine materialize file://PATH --ack-orphan --json --project-root <root>
```

Do not hand-edit a generated view as canonical state.

## 11. Read-only inspection and the trusted-code boundary

Engine-managed read-only inspection commands:

```text
status diff explain history graph resources verify
```

The engine does not intentionally mutate documentation/runtime state for these operations. However `docengine_project/**` is trusted/cooperative Python, not a sandbox. In particular `verify` may execute current builders/validators/renderers for reproducibility checks; arbitrary project callbacks can still perform external filesystem/network/process side effects. “Read-only” therefore describes the engine operation, not a security guarantee for untrusted Python.

The current project extension source revision is package-wide. A project-code edit may conservatively mark multiple deterministic builders `build_required` even when only one mirrored module changed.

## 12. Recovery and migration

If mutation is blocked by an interrupted transaction, inspect with `verify --json` and use:

```bash
docengine recover --json --project-root <root>
```

Never use `--force` automatically. `recover --force` is explicit destructive operator intent when post-crash state conflicts with journal evidence.

For recognized runtime-layout migration:

```bash
docengine migrate --json --project-root <root>
```

Unknown/future layouts or corrupt released evidence remain failures. Never delete `_dependency` to bypass migration.

## 13. Error handling

When `--json` is present, consume the canonical envelope. Do not parse human stderr/tracebacks as protocol. `warnings` are non-blocking; `errors` explain execution/usage failure; domain-state evidence may live inside `data` (for example verification findings). `meta.status` and `meta.exit_code` remain stable machine fields.


## Nested field authoring

The FIELD_DEPENDENCIES route also supports `document`, `input_path`, `computed_path` and `read_path` with JSON Pointers. Bind canonical raw documents before registration, declare independent child providers, then compose intermediate/root objects. Atomic parent and child ownership may not overlap. The nested fixture is `examples/nested_field_project`; formulas remain mirrored project code. Runtime BuildOperation reuse is automatic for CLI commands and does not permit hidden I/O or persistent global caches. Preserve existing internal IDs when upgrading a populated project; path renames require an explicit compatibility route.

Before choosing a source, follow the provider decision table in FIELD_DEPENDENCIES. Reuse the prepared helper and implement the project's source map/formulas/view builders from its stated requirements. A missing raw-only field cannot justify guessing a producer, changing the generic runtime, or copying generated values into raw data. An override declares input authority; add it only when that authority is part of the project contract. For an unavailable source/cycle/shape/old-target error, follow the recovery table and finish with sync/verify.
