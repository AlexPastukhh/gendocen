# Markdown-derived field example — additive authoring support

## Goal and scope

Implements the copyable example proposed in applicability review
`R-2026-10-08-01 / MP-Q1` (formerly Q-3). Ordinary documentation authors can reuse
an existing tracked Markdown → explicitly bounded derived field → FieldPlan →
rendered quotation route. Project code owns source meaning, bounds, formulas and
registrations; engine code supplies execution, provenance, updates and attention.

The source remains canonical Markdown. `file://` remains whole-file only; a
derived `resource://source/policy#/reuse` exposes the selected slice. The example
uses the existing unchanged FieldPlan helper and mirrored target modules. Its two
semantic consumers deliberately demonstrate different sufficient source scopes.

Runtime and active wheel remain `0.1.0.dev25`; persisted layout, schemas and P0–P8
acceptance history remain unchanged. This is an example/documentation addition,
not a generic Markdown parser, importer, Helper integration, automatic semantic
approval or complete migration of a real methodology corpus.

## Contents and discovery

- [Example and instructions](../examples/markdown_field_project/README.md).
- [Standalone disposable checks](../examples/markdown_field_project/check_example.py).
- [Repository regression](../tests/test_markdown_field_project.py).
- Discovery through root README, WF06, Field Dependencies and Semantic Review.
- Native anchors remain navigation. Author-selected extent and missing/duplicate/
  inverted bounds are explicit; relative-link rebasing belongs to a relocating
  renderer when required by the selected passage.

## Acceptance scenarios

1. Fresh sync creates the generated quotation and requests semantic review;
   synthetic demo decisions establish baseline; graph/verify show tracked inputs.
2. Adjacent edit preserves bounded quotation bytes and its semantic consumer;
   the intentionally whole-file consumer requires review.
3. Selected edit updates quotation and requests review of both semantic consumers.
4. A second source edit rejects a previously obtained review token.
5. Edited target rejects `still-valid`, then accepts a fresh `updated` decision.
6. Missing/duplicate start or end, and inverted bounds, fail with old output retained.
7. Generated drift is detected and restored through normal sync.

All demo validation decisions are explicitly synthetic CI actions confined to a
temporary fixture. Their success does not validate real project meaning. Runtime
CLI outcomes are saved before assertions for later diagnosis.

## Verification

Local verification completed with Python 3.12 and the installed `0.1.0.dev25`
wheel: all 11 executable scenarios and 39 CLI calls passed. Actual command
outcomes are retained in
[`evidence/MARKDOWN_FIELD_EXAMPLE/local-installed-example.json`](evidence/MARKDOWN_FIELD_EXAMPLE/local-installed-example.json).
The complete source suite passed: **384 passed / 1 platform skip**. Release
lifecycle, spec audit, axis audit and normalized performance release checks also
passed. Runtime/wheel bytes are unchanged.

Authoritative Windows application and verification completed on 2026-10-08.
The isolated installed wheel passed all **11 scenarios / 39 CLI calls**. The
ordinary source suite reported **364 passed, 1 skipped, 20 deselected in 223.25s (0:03:43)**. Release lifecycle, spec audit,
axis audit and release-manifest validation passed. Verification left checkout
contents, Git status and HEAD unchanged. See the actual
[Windows verification report](evidence/MARKDOWN_FIELD_EXAMPLE/windows-verification.json)
and [installed-wheel command report](evidence/MARKDOWN_FIELD_EXAMPLE/windows-installed-example.json).

The 20 unchanged `requires_symlink` tests were deliberately deselected in this
ordinary Windows run; their earlier privileged **20/20** acceptance is documented
in the [maintained symlink profile](SYMLINK_TEST_WORKFLOW.md). This addition changes
no symlink/security behavior and does not claim to repeat that profile.

All source/wheel checks used temporary fixture storage outside the checkout.
Host application checked the original manifest, all baseline hashes, inventory,
target hashes and new-file absence before writing. Backups and guarded writes
preserved existing user changes. Runtime/wheel bytes remain unchanged.
