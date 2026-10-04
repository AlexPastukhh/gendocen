# Empty explicit-root and WF03 hardening — v0.37

## Scope

Targeted post-acceptance runtime + documentation/test correction on top of v0.36. This correction intentionally changes one runtime validation rule: an explicitly supplied project root must be non-empty. Persisted-state, machine-output, and runtime-layout schema versions are unchanged.

## Trigger

Independent full-package review and meta-review confirmed three remaining defects:

1. an empty explicit `--project-root` (for example `--project-root="$ROOT"` with `ROOT=""`) was resolved as `.` and reported as `source=explicit`, so mutating commands could operate on the caller's cwd project instead of failing closed;
2. the zero-context documentation guard did not require a non-empty root value and did not split single `|` / `&` shell operators, so a quoted/value masquerade or adjacent command could evade the intended invariant;
3. WF03 was not fully self-contained for the original WR-33 fresh-project acceptance path because A/B were shown as payloads rather than valid resource envelopes, C was described without a complete descriptor example, and the workflow did not itself finish the mutation/check/sync/verify loop.

## Baseline change

This is an explicit post-v0.36 runtime hardening change, not a retroactive claim that v0.36 introduced the defect. The empty-root behavior existed in the accepted runtime before this correction. The clean-chat/root-safety goal established later in the correction chain exposed that fail-open behavior as unsafe. Runtime build therefore advances from `0.1.0.dev20` to `0.1.0.dev21`; no P9 phase is created.

## Corrections

- `discover_roots()` rejects empty/whitespace-only explicit string project roots with `RootDiscoveryError` before cwd resolution.
- `initialize_project()` rejects the same input with `ProjectInitializationError` before ancestor/cwd project selection or filesystem mutation.
- CLI commands consequently return usage/config exit `4` for an empty explicit project root instead of treating cwd as explicit.
- the zero-context guard requires `--project-root` to have a non-empty shell value, preserves quote awareness, and splits `|` / `&` in addition to `&&` / `||` / `;` / newline.
- WF03 now includes minimal valid A/B envelopes, a complete C derived descriptor, builder/registration steps, and an explicit `check -> sync -> verify` completion path with the original `A.field3 + B.field2` computation.
- the bundled runtime wheel is rebuilt as `generic_documentation_engine-0.1.0.dev21-py3-none-any.whl` and verified by offline installation.

## Identity

- documentation/spec package: `0.37.0-p8-empty-root-wf03-hardening`;
- runtime build: `0.1.0.dev21`;
- target stable runtime remains `0.1.0`;
- engine phase remains P8 accepted; no P9.

## Validation

Final frozen-source validation after the correction:

- full pytest: **272 passed, 1 skipped, 276 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**, 628 tracked / 628 actual files;
- clean offline install of `dist/generic_documentation_engine-0.1.0.dev21-py3-none-any.whl`: **PASS**; `docengine --version` reports `0.1.0.dev21`; `pip check` reports no broken requirements.

After this record update the manifest is regenerated again. The final archive is independently unpacked and revalidated before delivery.
