# Clean-chat onboarding correction — v0.31

## Scope

This is a documentation/onboarding/test-only correction on top of v0.30. Runtime semantics remain `0.1.0.dev20` and `src/docengine/**` is unchanged.

## Goal

A zero-context human/AI session must be able to begin correctly without this conversation history:

1. distinguish project authoring from engine maintenance;
2. establish a working Python/docengine environment;
3. find or explicitly select the intended project root;
4. inspect unfamiliar project Python before commands that load it;
5. determine visible-document ownership;
6. route the requested task to one WF01–WF12 workflow rather than reading the entire manual;
7. use the existing selective sync/review/verify loop.

## Changes

- added `docs/CLEAN_CHAT_QUICKSTART.md`;
- README now routes zero-context users there first and includes a compact task router;
- `AI_USAGE_PROTOCOL.md` now includes the environment/root/trust preflight;
- `CORE_WORKFLOWS.md` includes a task router and explicitly treats the quickstart as its prerequisite for unfamiliar projects;
- `REPOSITORY_WORKFLOW.md` uses the same clean-chat route;
- documentation regression tests enforce this route and trust-preflight wording.

## Security/trust boundary

No sandbox is added. The quickstart makes the existing trusted/cooperative Python boundary operational: inspect the configured `project_package` before running commands that load it. `resources` is the initial inventory command because current v0.1 executes it without loading project extensions; it is not builder-registration proof.

## Identity

- documentation/spec package: `0.31.0-p8-clean-chat-onboarding-correction`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final validation after the onboarding/test changes:

- full pytest on the final source tree: `251 passed, 1 skipped, 255 subtests passed`;
- `tools/audit_spec.py`: PASS;
- `tools/audit_axes.py --json`: PASS, no findings;
- `tools/release_check.py --json`: PASS, no findings;
- `tools/benchmark_release.py --json`: PASS, 10,000 targets / 50,000 edges within budget;
- `tools/release_manifest.py validate`: PASS.

The manifest is regenerated after this record update. The release archive is also checked from an independently unpacked copy before delivery.
