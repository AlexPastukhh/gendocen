# P2 Acceptance Review — Builders, derived objects and tracked reads

Date: 2026-10-02
Decision: **ACCEPTED AFTER INDEPENDENT RE-AUDIT**
Runtime build: **0.1.0.dev5**
Next phase: **P3 — Dependency receipts, baselines, comparators, diff and state**

## Implemented

- project-local `project_package` configuration and confined extension loading;
- dotted project-package relative-import semantics under an isolated private runtime prefix;
- explicit `BuilderRegistry` with decorator convenience;
- dependency-aware `BuildContext.read/get` with per-dependency comparator override and builder-level default;
- explicit `untracked_read(..., reason=...)` escape hatch;
- machine-readable `tracking_assurance="cooperative"` so `audit_complete` is not misread as sandbox proof;
- immutable `DerivedObject` and deterministic `BuildProvenance`;
- project-code source revision (`builder_revision`) in provenance so later phases can invalidate on formula/helper changes;
- raw+raw, raw+derived and derived+derived recursive builds;
- direct dependency evidence at exact field/resource/plain-file granularity;
- `file://` restricted to plain canonical Markdown; structured/runtime/generated storage cannot be used as a file-ref bypass;
- transitive propagation of upstream `audit_complete=false`;
- deterministic exact cycle diagnostics;
- documentation-owned `derived_descriptor` requirement only for documentation-owned/materialized derived targets;
- internal-only derived targets may exist without JSON;
- every existing `derived_descriptor` must resolve to a registered builder and is never treated as raw fallback data;
- canonical `ResourceRef` identity enforced for both parsed strings and direct object construction;
- JSON-compatible derived-output validation;
- unrelated product+tax fixture proving domain independence;
- `DERIVED_OBJECT.schema.json` serializable envelope contract.

P2 intentionally does **not** persist receipts, baselines, dependency state/events or built derived objects. It also does not wire the stateful `rebuild` CLI; those boundaries remain P3/P5/P6.

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| P2-A1 new derived object; raw inputs unchanged | PASS | `tests/test_builders.py`, `src/docengine/builders.py` |
| P2-A2 only actual tracked reads captured | PASS | exact-read tests + product/tax fixture + file-boundary regressions |
| P2-A3 raw+raw/raw+derived/derived+derived | PASS | chain tests |
| P2-A4 deterministic cycle path | PASS | cycle tests + `plan/evidence/P2/cycle_diagnostic.txt` |
| P2-A5 unrelated domain same runtime | PASS | `examples/product_tax_project/`, clean-wheel evidence |
| P2-A6 repeated build equivalent output/provenance | PASS | deterministic repeat test; same code revision + same inputs |
| P2-A7 confined project code + documentation-owned output ownership | PASS | extension safety, internal-derived, descriptor symmetry and dotted-package tests |
| P2-A8 envelope/docs/wheel/package agree | PASS | schema tests, package audit, active dev5 wheel |

## Re-audit defects corrected

1. Internal-only derived targets were incorrectly forced to have JSON descriptors.
2. A `derived_descriptor` without a builder could silently behave like raw `{}` data.
3. `file://` could read `_structured`, future `_dependency`, or generated managed views and bypass canonical resource tracking.
4. Invalid/non-canonical `ResourceRef` objects could be constructed directly and registered even when their string form was not parseable canonically.
5. Dotted `project_package` was accepted by config but parent-relative imports did not work.
6. Builder/helper code revision was absent from provenance, leaving P3 unable to detect formula-only changes.
7. Comparator semantics were builder-wide even though future receipts require dependency-specific comparators.
8. `AI_USAGE_PROTOCOL.md` still described the P1 boundary after P2 acceptance.
9. `DEPENDENCY_MODEL.md` contained non-canonical `file://docs/...` examples even though file refs are documentation-root-relative.

All nine are corrected in this re-audited package and have regression evidence where executable behavior is involved.

## Explicit assurance boundary, not counted as a defect

Python project code is cooperative/trusted in v0.1; it is not sandboxed. A project builder that deliberately bypasses `BuildContext` can perform hidden I/O that the runtime cannot observe. This limitation is now machine-readable (`tracking_assurance="cooperative"`) and documented. `audit_complete=true` means no **known** gaps under the required context-usage contract, not proof that arbitrary Python performed no hidden I/O.

A stronger sandbox/restricted execution model is a possible future hardening feature, not silently assumed by P2.

## Test/evidence summary

See `plan/P2_AXIS_AUDIT.md`, `plan/P2_PACKAGE_AUDIT.md`, `plan/P2_REAUDIT.md` and `plan/evidence/P2/`.

## Additional independent re-audit closures

- `derived_descriptor` is metadata-only even through direct `ResourceCatalog.get/version`; it cannot become fake raw truth outside BuildEngine.
- dotted parent-imports-child package loading reuses the already-loaded verified child and does not execute the child twice.
- active handoff docs/runtime identity are checked against the current dev5 distribution; historical dev3 evidence remains historical rather than being rewritten.

These were confirmed executable/documentation defects, not speculative enhancements.

## Final re-audit addendum

A tenth confirmed defect was corrected before the final package: whole raw-resource dependency versions had followed physical JSON bytes/envelope metadata. They now hash canonical domain `data`; `source_hash` remains separate physical-source provenance.
