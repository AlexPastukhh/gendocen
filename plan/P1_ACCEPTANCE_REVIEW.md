# P1 Acceptance Review — Project, resource, storage and loader core

Date: 2026-10-02
Decision: **ACCEPTED**
Next phase after acceptance: **P2 — Builders, derived objects and tracked reads**

## Implemented

- versioned `docengine.toml` project configuration and safe root discovery;
- idempotent `docengine init` that creates engine directories without promoting plain Markdown;
- strict canonical JSON parser rejecting duplicate keys and non-standard numeric constants;
- project schema registry plus dependency-free `SchemaValidator` adapter/subset implementation;
- canonical `ResourceRef`/`FieldRef` parser/formatter with JSON Pointer support;
- deeply immutable generic `RawObject` values;
- managed resource loading from mirrored `docs/_structured/...`;
- explicit Markdown materialization ownership/path validation and project/docs confinement;
- deterministic resource catalog distinguishing `plain`, `managed`, `derived`, and `generated`;
- resource resolver and deterministic content version helpers;
- implemented `docengine resources` in human and versioned JSON forms;
- sample project config and project schemas;
- runtime distribution version advanced to `0.1.0.dev2` after the independent P1 axis audit.

P1 intentionally does **not** implement builders/tracked dependency reads, baselines/state/diff, semantic review, or actual materialization execution.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| P1-A1 Markdown remains first-class without JSON sidecars | PASS | `tests/test_p1_init.py`, `tests/test_p1_resources.py`, clean-venv plain project inventory |
| P1-A2 managed JSON validates and loads generically | PASS | `src/docengine/{schema,jsonio,objects,resources}.py`, sample schemas, runtime schema tests |
| P1-A3 materialization path is docs-root-relative/confined | PASS | mirrored-layout/path/symlink negative tests |
| P1-A4 refs round-trip and malformed refs fail | PASS | `src/docengine/refs.py`, `tests/test_refs.py` |
| P1-A5 raw objects immutable | PASS | `src/docengine/objects.py`, `tests/test_objects.py` |
| P1-A6 deterministic sample inventory human + JSON | PASS | `plan/evidence/P1/sample_resources.*`, clean-venv resource inventory |

## Emergent findings resolved during P1

1. Old documentation still contained dot-form resource URI examples even though Q1.4 had fixed namespace/path syntax. Docs and runtime were aligned to `resource://<namespace>/<id>#/<json-pointer>`.
2. A full `jsonschema` runtime dependency was not required for P1. Instead the engine exposes an adapter boundary and a strict documented stdlib subset that fails on unsupported keywords rather than silently skipping them.
3. The mirrored `_structured` layout is enforced for Markdown outputs rather than treated as prose-only guidance.
4. P1 uses a distinct current distribution identity; after post-acceptance safety fixes the active build is `0.1.0.dev2`, with historical wheels moved out of active `dist/`.
5. Axis review found symlink edge cases, including dangling `docengine.toml`; initialization/config/resource scanning now rejects unsafe cases and regression tests cover them.

## DAX review

Mapped P1 axes pass **for P1 scope** after independent correction: DAX01, DAX02, DAX03, DAX04, DAX05, DAX12, DAX17, DAX19, DAX20. Engine-wide closure remains partial until the later phases exercise builders, dependency runtime, materialization, recovery and final release verification. See `plan/P1_AXIS_AUDIT.md`.

## Distribution evidence

The final audited wheel `generic_documentation_engine-0.1.0.dev2-py3-none-any.whl` is the only active wheel in `dist/` and is installed into a fresh venv with no runtime dependencies. Installed CLI checks include:

- `docengine --version` → `0.1.0.dev2`;
- `pip check` → no broken requirements;
- `docengine resources --project-root examples/sample_project --json` → deterministic inventory;
- first `docengine init` → `initialized`;
- second `docengine init` → `already_initialized`;
- a plain Markdown-only project remains plain in `resources` output.

The original candidate suite passed; an independent post-acceptance audit then found and fixed additional axis defects. The corrected dev2 candidate passes expanded regression and clean-install checks; final manifest/no-mutation verification is documented in `plan/P1_PACKAGE_AUDIT.md`.

## Post-acceptance independent review

A second axis-by-axis review found and fixed malformed ancestor marker fallback, reserved-tree overlap, materialization into reserved state, float overflow in strict JSON, active multi-wheel ambiguity and missing P1 DAX20 mapping. See `plan/P1_POST_ACCEPTANCE_AXIS_REVIEW.md`.

## Final corrected-package verification

Independent axis corrections are covered by the final **55 tests / 130 subtests**, `SPEC AUDIT OK`, clean installed dev2 checks and exactly-one-current-wheel distribution audit.
