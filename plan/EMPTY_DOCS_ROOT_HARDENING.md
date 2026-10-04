# Empty explicit documentation-root hardening — v0.38

## Scope

Targeted post-v0.37 runtime + documentation/test correction. This changes one root-validation rule: an explicitly supplied documentation root must be non-empty. Persisted-state, machine-output, and runtime-layout schema versions are unchanged.

## Trigger

Independent full-package review of v0.37 found a pre-existing inconsistency outside the three v0.37 correction targets: `init --docs-root=` treated the empty override as the default `docs/`, while ordinary commands treated the same explicit value as `.` (the project root). The behavior existed before v0.37; v0.37 did not introduce it.

The inconsistency was operationally significant: after initialization under `docs/`, later commands using `--docs-root=` could create a second `_dependency/` tree at project root, and `verify --docs-root=` could return success while drift existed under the configured `docs/` tree because verification was pointed at the wrong documentation universe.

## Baseline change

The clean-chat/root-safety goal is refined symmetrically: explicit string overrides for both `--project-root` and `--docs-root` fail closed when empty or whitespace-only. This is an additive runtime hardening rule, not a retroactive claim that v0.37 or the documentation correction chain introduced the old behavior. Runtime build advances from `0.1.0.dev21` to `0.1.0.dev22`; no P9 phase is created.

## Corrections

- `discover_roots()` rejects empty/whitespace-only explicit string documentation roots with `RootDiscoveryError` before path resolution.
- `initialize_project()` rejects the same input with `ProjectInitializationError` before config/runtime filesystem mutation.
- CLI commands consequently return usage/config exit `4` for an empty explicit documentation root instead of selecting project root/default docs inconsistently.
- initialization and ordinary commands now share the same explicit-empty policy; omitting `--docs-root` still selects configured/default documentation root normally.
- behavioral regressions prove `resources`, `sync`, and `verify` fail before root-level `_dependency` creation, and that the former false-success verify path cannot occur.
- the bundled runtime wheel is rebuilt as `generic_documentation_engine-0.1.0.dev22-py3-none-any.whl` and verified by offline installation.

## Identity

- documentation/spec package: `0.38.0-p8-empty-docs-root-hardening`;
- runtime build: `0.1.0.dev22`;
- target stable runtime remains `0.1.0`;
- engine phase remains P8 accepted; no P9.

## Validation

Final frozen-source validation:

- full pytest: **275 passed, 1 skipped, 279 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**, 629 tracked / 629 actual files;
- clean offline install of `dist/generic_documentation_engine-0.1.0.dev22-py3-none-any.whl`: **PASS**; `docengine --version` reports `0.1.0.dev22`; `pip check` reports no broken requirements;
- installed-wheel CLI probes: empty `--docs-root=` during `init` returns exit `4` with **zero filesystem writes**, and whitespace-only `--docs-root` during `resources` returns exit `4`.

After this record update the manifest is regenerated again. The final archive is independently unpacked and revalidated before delivery.
