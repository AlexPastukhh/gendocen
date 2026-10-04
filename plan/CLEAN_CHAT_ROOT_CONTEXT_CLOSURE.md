# Clean-chat root-context closure — v0.34

## Scope

Documentation/onboarding/test-only correction on top of v0.33. Runtime semantics remain `0.1.0.dev20`; `src/docengine/**` is unchanged.

## Trigger

Independent post-v0.33 review confirmed that the explicit-root correction was incomplete in three concrete ways:

1. `CORE_WORKFLOWS.md` still contained imperative inline/diagram project commands such as `resources`, `graph`, `check`, and `recover` without `--project-root <root>`, so a clean chat could establish project A and then fall back to cwd project B;
2. `examples/sample_project/README.md` used `--project-root .` before establishing the copied fixture as cwd, so a literal walkthrough from the release root inspected the engine repository instead of the sample;
3. the v0.33 static guard primarily recognized command lines beginning with `docengine ` and therefore missed imperative inline/diagram commands and did not verify that fixture cwd was established before `--project-root .`.

## Corrections

- `docs/CORE_WORKFLOWS.md` now keeps explicit `--project-root <root>` on copyable imperative project commands, including ownership discovery, pre-rebuild inspection, WF01 inventory, and recovery diagrams;
- `examples/sample_project/README.md` establishes a disposable copy and `cd` before the first `--project-root .` command, and all later commands explicitly continue in that fixture;
- the documentation guard now checks fenced commands, inline backtick command spellings, and diagram commands; conceptual references use bare command names such as `verify`, so a full `docengine <project-command>` spelling in zero-context docs is always root-explicit;
- fixture-ordering regression coverage requires `cd` into each runnable copied fixture before its first `--project-root .` command;
- the adversarial two-project behavioral test now executes `resources → graph → check → sync → verify` against explicit project A while cwd is project B, asserts B project Python is not imported, and asserts B remains byte-for-byte unchanged.

## Identity

- documentation/spec package: `0.34.0-p8-clean-chat-root-context-closure`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final source-tree validation after the correction:

- full pytest: **258 passed, 1 skipped, 255 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**.

The manifest is regenerated after this record update. The final archive is independently unpacked and revalidated before delivery.
