# Clean-chat explicit-root consistency correction — v0.33

## Scope

Documentation/onboarding/test-only correction on top of v0.32. Runtime semantics remain `0.1.0.dev20`; `src/docengine/**` is unchanged.

## Trigger

Independent post-v0.32 review reproduced three root-selection defects:

1. the quickstart established an explicit intended project root, but downstream `CORE_WORKFLOWS`, `AI_USAGE_PROTOCOL` and runnable example commands could drop it and fall back to cwd/upward discovery;
2. the quickstart incorrectly presented `--docs-root` as an alternative project-root selector;
3. rootless `docengine init` in a directory nested below another gendocen project could select the ancestor and return `already_initialized` instead of creating the intended child project.

## Corrections

- zero-context generic project commands use `--project-root <root>` consistently;
- runnable fixture commands use `--project-root .` after explicitly `cd`-ing into the copied fixture;
- `--project-root` alone is documented as the explicit project selector; `--docs-root` is documented as a documentation-root override confined inside the selected project;
- new-project initialization uses `docengine init --project-root /path/to/intended/project --json`;
- regression coverage includes a two-project adversarial test proving an explicit intended root remains authoritative even when cwd points at another valid project, plus a nested-init test and static checks for rootless copyable commands.

## Identity

- documentation/spec package: `0.33.0-p8-explicit-root-consistency-correction`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final source-tree validation after the correction:

- full pytest: **257 passed, 1 skipped, 255 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**.

The manifest is regenerated after this record update. The final archive is unpacked independently and revalidated before delivery.
