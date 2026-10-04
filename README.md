# Generic Documentation Engine — v0.39 project-config root-policy sync

Target stable runtime: **v0.1**. Current engine build: **0.1.0.dev22**.

`gendocen` is a Markdown-first documentation composition engine. Most Markdown may remain plain. Selected content can have canonical structured JSON, project builders can compose new objects from exact fields/resources, the runtime records those dependencies, and upstream changes invalidate only the evidence that actually changed. Deterministic targets can be explicitly rebuilt; semantic targets require human/AI review rather than automatic prose rewriting.

P0–P8 runtime semantics remain accepted. v0.31 added the zero-context onboarding layer; v0.32 finalized bootstrap/offline installation; v0.33 introduced the explicit-root invariant; v0.34 closed downstream root-context gaps; v0.35 hardened root-context regression detection; and v0.36 finalized documentation/release consistency; v0.37 rejects empty explicit project roots fail-closed, completes the fresh-project WF03 guide, and strengthens root-command regression parsing; v0.38 applies the same fail-closed rule to explicit documentation-root overrides so `init`, inspection, mutation, and verification cannot disagree on an empty `--docs-root`; v0.39 synchronizes the active project-configuration reference with that accepted root policy. Runtime remains `0.1.0.dev22`; persisted/machine schemas remain unchanged.

## Core mental model

```text
plain Markdown                         structured project data
                                         docs/_structured/<path>.json
                                                   ↓
                                              RawObject
                                                   ↓ tracked reads
project code                               deterministic builder
  docengine_project/builders/<path>.py           ↓
                                            DerivedObject (transient)
                                                   ↓
                                               renderer
                                                   ↓
                                           docs/<path>.md

tracked reads / semantic rules → receipts + baselines → check/invalidation
```

Deterministic change:

```text
input changed → build_required → explicit rebuild/sync → valid
```

Semantic change:

```text
context changed → review_required/stale → human/AI review → validate → valid
```

## Start here — learn and use the engine

1. [`docs/CLEAN_CHAT_QUICKSTART.md`](docs/CLEAN_CHAT_QUICKSTART.md) — **zero-context first start**: environment, project root, trust preflight, ownership and task router.
2. [`docs/CORE_WORKFLOWS.md`](docs/CORE_WORKFLOWS.md) — real-life workflows and correct authoring guide.
3. [`examples/product_tax_project/README.md`](examples/product_tax_project/README.md) — runnable field-level deterministic build/invalidation.
4. [`examples/sample_project/README.md`](examples/sample_project/README.md) — runnable semantic-review/ownership fixture.
5. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — object/dependency/presentation boundaries.
6. [`docs/PRINCIPLES.md`](docs/PRINCIPLES.md) — stable principles.
7. [`docs/USE_CASES.md`](docs/USE_CASES.md) — atomic normative `DOCxx` contracts.
8. [`docs/CODE_MODEL.md`](docs/CODE_MODEL.md), [`docs/DEPENDENCY_MODEL.md`](docs/DEPENDENCY_MODEL.md), [`docs/MATERIALIZATION_MODEL.md`](docs/MATERIALIZATION_MODEL.md) — reference models.
9. [`docs/AI_USAGE_PROTOCOL.md`](docs/AI_USAGE_PROTOCOL.md) — machine operating protocol.


## Quick task router

| You need to... | Start with |
|---|---|
| create a deterministic dependency / generated document | `CLEAN_CHAT_QUICKSTART` → WF03 |
| update outputs after structured inputs changed | WF04 |
| review semantic prose after its assumptions changed | WF05 |
| aggregate many resources | WF07 |
| understand why something is affected | WF09 |
| verify/regenerate a project | WF10 |
| recover/migrate runtime state | WF11 / WF12 |
| maintain the gendocen engine itself | `START_HERE_AGENT.md` |

For an unfamiliar project, do the environment/project-root/trust preflight in `CLEAN_CHAT_QUICKSTART.md` **before** commands that load `docengine_project/**`.

## Normal project-authoring layout

```text
docs/<logical/path>.md
docs/_structured/<logical/path>.json
docengine_project/builders/<logical/path>.py
docengine_project/dependency_rules/<logical/path>.py
```

Project code is registered through `docengine_project` and lives outside `docs/`. Ordinary project dependency authoring should not require edits to `src/docengine/**`.

Project Python is trusted/cooperative, not sandboxed. The documented structure and tracked-read discipline reduce accidental core damage; they do not physically prevent arbitrary Python side effects.

## Normal AI/author loop

```text
edit canonical data/project code
→ docengine sync --project-root <root> --json
   ├─ selective deterministic rebuild/materialization
   └─ semantic attention remains unresolved
→ explain/diff + human/AI review + validate
→ sync
→ verify
```

Run `docengine check --project-root <root> --json` separately when you want to inspect changes before deterministic rebuild. `docengine sync --project-root <root> --all --json` broadens materialization; it does not force-rebuild every valid builder.

## Operational CLI

```text
init status check diff explain sync rebuild validate materialize verify history graph resources recover migrate
```

## Maintainer / release handoff

If you are continuing engine/release maintenance rather than learning project authoring, read:

1. `START_HERE_AGENT.md`
2. `OPEN_QUESTIONS_AND_AMBIGUITIES.md`
3. `docs/RELEASE_GATE.md`
4. `docs/PHASE_ACCEPTANCE_MODEL.md`
5. `docs/REPOSITORY_WORKFLOW.md`
6. `plan/GITHUB_CHECKOUT_PORTABILITY_AUDIT.md`
7. `plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md`
8. `plan/REPOSITORY_PERSISTENCE_AUDIT.md`
9. `plan/P8_POST_ACCEPTANCE_CONSISTENCY_REVIEW.md`
10. `plan/P8_FINAL_AXIS_AUDIT.md`
11. `plan/phase_records/P8_EXECUTION_RECORD.json`

Historical phase/evidence records are not rewritten to make current documentation prettier. Post-acceptance use-case normalization is additive via `spec/registries/USE_CASE_COVERAGE_AMENDMENTS.json`.

## Final release tooling

```bash
python -m pytest -q
python tools/release_check.py --json
python tools/benchmark_release.py --json
python tools/release_manifest.py validate --json
python tools/audit_axes.py --json
python tools/audit_spec.py
```

No external `PYTHONPATH` setup is required for the benchmark command.

## Package identity

- specification/runtime package: `0.39.0-p8-project-config-root-policy-sync`;
- runtime build: `0.1.0.dev22`;
- target stable runtime: `0.1.0`;
- persisted-state schema: `1.0.0`;
- machine-output schema: `2.0.0`;
- runtime-layout schema: `1.0.0`;
- current engine phase: `P8 accepted`; v0.39 is a documentation-only post-acceptance project-config root-policy synchronization;
- next engine phase: none — this is not P9.

## Git persistence and portability

The archive is intended to be usable in a private Git repository. Read `docs/REPOSITORY_WORKFLOW.md` before the first commit. `.git/` and local caches are excluded from release inventory; repository controls and the active wheel remain tracked.

The supported repository regression surface includes Ubuntu/Python 3.11 and Windows/Python 3.14. POSIX readers may share the runtime lock; Windows v0.1 intentionally serializes readers safely. Git-normalized UTF-8 text must use LF before manifest generation, and fresh-checkout manifest validation remains a first-class release invariant.
