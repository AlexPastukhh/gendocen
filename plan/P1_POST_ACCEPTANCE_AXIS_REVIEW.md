# P1 Post-Acceptance Independent Axis Review

Date: 2026-10-02
Decision after corrections: **P1 REMAINS ACCEPTED**
Runtime build after corrections: **0.1.0.dev2**

## Why this review exists

This review intentionally did not trust the previously recorded phase-local PASS values. Each P1-relevant DAX axis was checked again against current code, negative cases, distribution contents and handoff behavior.

Phase-local `PASS` means that the slice of the axis implemented or materially touched by P1 is currently satisfied. Global release-gate closure remains a P8 responsibility.

## Findings discovered by the independent review

### F-P1-AX-01 — malformed ancestor config marker could be silently skipped

**Axes:** DAX03, DAX04.

`_find_project_root()` previously used only `is_file()` to recognize `docengine.toml`. A dangling symlink or a directory named `docengine.toml` in an ancestor could therefore be skipped, causing a nested cwd to be treated as a fresh project root. `docengine init` could then initialize the wrong nested project.

**Fix:** lexical marker presence now stops upward discovery; the config loader then rejects symlink/non-file markers explicitly. Regression tests cover dangling and non-file ancestor markers.

### F-P1-AX-02 — reserved documentation trees could overlap

**Axes:** DAX02, DAX04.

`structured_dir` and `dependency_dir` could previously be equal or ancestor/descendant paths, including `.`. That breaks the intended separation between canonical structured documentation and runtime dependency state.

**Fix:** the two configured trees must be dedicated, disjoint subtrees and use portable `/` path separators.

### F-P1-AX-03 — materialization could target canonical/runtime state

**Axes:** DAX02, DAX04.

A non-Markdown materialization target could previously point inside `_structured` or `_dependency` while still remaining inside the documentation root. A later materializer could therefore overwrite canonical JSON or dependency runtime state.

**Fix:** every renderer is prohibited from targeting either reserved subtree. Regression tests cover both structured and dependency targets.

### F-P1-AX-04 — strict JSON could still produce non-finite runtime floats

**Axis:** DAX03.

Literal `NaN`/`Infinity` was already rejected, but a standards-valid numeric literal such as `1e999` could overflow Python `float` and become `inf`, creating unstable/non-canonical runtime state.

**Fix:** strict parsing now rejects float literals outside the finite runtime range.

### F-P1-AX-05 — active distribution contained historical wheels

**Axes:** DAX03, DAX20.

The accepted package had both `0.1.0.dev0` and `0.1.0.dev1` under active `dist/`. A normal command such as `pip install dist/*.whl` therefore produced a dependency-resolution conflict between two versions of the same package.

**Fix:** active `dist/` now contains exactly one current wheel. Historical wheels are retained under `plan/evidence/<phase>/artifacts/`. `tools/audit_spec.py` now checks exactly-one-current-wheel, pyproject/engine/manifest version consistency, wheel filename identity and wheel METADATA version. Runtime build advanced to `0.1.0.dev2` because runtime safety code changed during this audit.

### F-P1-AX-06 — DAX20 was omitted from P1 mapping

**Axis:** DAX20.

P1 creates a new wheel, manifest, README, START_HERE and transferable archive, so handoff integrity is materially touched by the phase. Omitting DAX20 from the mapped axes allowed the stale-wheel defect above to avoid the formal phase-axis checklist.

**Fix:** P1 now maps and reviews DAX20. P8 still performs the global consolidated release review.

## Axis results after corrections

| Axis | P1 result | Global status after P1 | Independent-review conclusion |
|---|---|---|---|
| DAX01 Markdown-first boundary | PASS | PARTIAL | Plain Markdown remains usable without JSON sidecars; `init` does not promote it. |
| DAX02 Documentation ownership/layout | PASS after fixes | PARTIAL | Structured/runtime trees are docs-owned, mirrored where required, disjoint and protected from generated writes. |
| DAX03 Resource/schema/version integrity | PASS after fixes | PARTIAL | Strict refs/schema/resource IDs/version identity hold; malformed marker and non-finite JSON issues were fixed. |
| DAX04 Path confinement/data safety | PASS after fixes | PARTIAL | Traversal, symlink escapes, malformed-root fallback and reserved-tree output hazards are rejected. Transactional writes remain P7. |
| DAX05 Raw/derived separation | PASS | PARTIAL | P1 raw values are deeply immutable and no derived fields are injected; derived provenance begins P2. |
| DAX12 CLI contract/boundaries | PASS | PARTIAL | `init`/`resources` have real deterministic human/JSON semantics; later commands remain explicit stubs. |
| DAX17 Domain independence | PASS | PARTIAL | Runtime remains domain-neutral and project schemas are external. Builder extension paths are P2. |
| DAX19 Test assurance | PASS after expanded regression coverage | PARTIAL | Positive and negative tests now cover the independent-review defects as well as prior P1 behavior. |
| DAX20 Release/handoff integrity | PASS after fixes | PARTIAL | Active distribution is unambiguous; current docs identify the P1 boundary; manifest/version/wheel identity is machine-checked. Global closure remains P8. |

## Source-checkout test command

The canonical source-checkout command remains:

```bash
python -m pytest -q
```

A bare `python -m pytest -q` from the source checkout is now a supported canonical execution mode. The project config adds `src` to pytest's import path so a receiving chat/agent does not need hidden shell state or a manual `PYTHONPATH`.

## Acceptance conclusion

The independent audit found real defects, all within P1 scope, and they were corrected with regression coverage. No unresolved P1-scope axis finding remains after the final test/spec/distribution/manifest rerun. P1 remains `accepted`; engine-wide release-gate closure remains partial until later phases and P8.

## Continuation after interrupted audit

The interrupted independent review exposed one unresolved DAX19 gap in the packaged checkout: the source tree required an implicit `PYTHONPATH=src` to collect tests. This is now corrected. `python -m pytest -q` works directly from project root through explicit pytest configuration.

The final DAX20 pass was also strengthened: `audit_spec.py` now checks that the active wheel's `docengine/*.py` payload is byte-for-byte consistent with `src/docengine/*.py`, and rejects a leftover top-level `build/` directory in a transferable package.

### Final rerun evidence

- Source checkout: `python -m pytest -q` -> **56 passed, 130 subtests passed**.
- Active wheel/source parity: **13 runtime Python modules matched byte-for-byte**.
- Fresh venv install from the single active wheel: PASS; `pip check`: PASS.
- Installed CLI: `docengine 0.1.0.dev2`; sample `resources --json`: PASS; fresh project `init` -> `initialized` then `already_initialized`.
- Final manifest/spec/ZIP checks are release-package gates for this audited revision.
