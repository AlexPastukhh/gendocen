# Project-config explicit-root policy synchronization — v0.39

## Scope

Documentation/test/release-evidence correction on top of v0.38. Runtime remains `0.1.0.dev22`; `src/docengine/**` is unchanged. Persisted-state, machine-output, and runtime-layout schemas are unchanged.

## Trigger

Independent full-package review of v0.38 confirmed the empty explicit documentation-root runtime hardening but found one active-reference documentation gap: `docs/PROJECT_CONFIG.md` still stated the non-empty rule only for explicit project roots, while `CLEAN_CHAT_QUICKSTART.md` and `CLI_CONTRACT.md` already stated the accepted symmetric rule for explicit project and documentation roots.

## Correction

`docs/PROJECT_CONFIG.md` now states the accepted policy directly:

- explicit string `--project-root` and `--docs-root` overrides must be non-empty and non-whitespace;
- empty explicit root values are usage/config errors (CLI exit `4`), not fallback/default selection;
- a non-empty documentation-root path may still be absent for an empty/uninitialized documentation tree, preserving the accepted P6 behavior;
- explicit `--docs-root .` remains valid and intentionally selects the project root as the documentation root.

No new runtime requirement is introduced. This is synchronization of an active reference with the already accepted v0.38 behavior.

## Identity

- documentation/spec package: `0.39.0-p8-project-config-root-policy-sync`;
- runtime build: `0.1.0.dev22` unchanged;
- engine phase remains P8 accepted; no P9.

## Validation

Final frozen-source validation:

- full pytest by test-file groups: **276 passed, 1 skipped, 279 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**, 630 tracked / 630 actual files.

The final archive is independently unpacked and revalidated before delivery.
