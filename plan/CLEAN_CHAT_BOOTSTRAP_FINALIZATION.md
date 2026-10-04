# Clean-chat bootstrap finalization — v0.32

## Scope

This is a documentation/onboarding/test-only correction on top of v0.31. Runtime semantics remain `0.1.0.dev20` and `src/docengine/**` is unchanged.

## Trigger

Independent post-v0.31 clean-room review found two remaining practical onboarding defects:

1. a fresh offline virtual environment could not follow the documented editable source install because the build backend was not locally available, even though the release already ships a usable runtime wheel;
2. the final `check` / `sync --all` examples dropped the explicit `--project-root <root>` discipline established earlier for unfamiliar repositories.

## Corrections

- `docs/CLEAN_CHAT_QUICKSTART.md` documents the exact bundled-wheel offline install command for ordinary runtime use and distinguishes it from editable engine-development installation;
- the quickstart keeps `--project-root <root>` explicit for `check` and `sync --all`;
- README command examples use the same explicit-root discipline;
- documentation regression tests enforce both invariants.

## Identity

- documentation/spec package: `0.32.0-p8-clean-chat-bootstrap-finalization`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final source-tree validation:

- full pytest: **253 passed, 1 skipped, 255 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate`: **PASS**.

Independent offline-bootstrap probe in a fresh virtual environment:

- `python -m pip install --no-index dist/generic_documentation_engine-0.1.0.dev20-py3-none-any.whl`: **PASS**;
- `docengine --version`: `0.1.0.dev20`;
- `python -m pip check`: **PASS**.

The manifest is regenerated after this record update. The final archive is then unpacked independently and revalidated before delivery.
