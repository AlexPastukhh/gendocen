# Clean-chat root guard hardening — v0.35

## Scope

Documentation-test/release-evidence correction on top of v0.34. Runtime semantics remain `0.1.0.dev20`; `src/docengine/**` is unchanged. The shipped zero-context documentation already satisfied the explicit-root invariant at the start of this correction.

## Trigger

Independent post-v0.34 review found that the regression guard was weaker than the invariant it claimed to enforce:

1. a compound shell line such as `docengine check --project-root <root> --json && docengine sync --json` could pass because one `--project-root` anywhere in the captured line protected a second rootless project command;
2. executable plain prose such as "Run docengine resources --json now." could evade a guard focused on fenced/backtick/diagram forms.

These were guard-coverage defects, not defects in the current v0.34 zero-context command text.

## Corrections

- the zero-context guard scans all relevant documentation text for every full `docengine <project-command>` occurrence rather than only selected Markdown syntaxes;
- each occurrence is evaluated against its own shell-like command segment, so `&&`, `||`, and `;` cannot let one explicit root mask another rootless command;
- backslash-newline continuation remains one command, so valid multiline explicit-root commands continue to pass;
- adversarial regression cases cover compound `&&` / `||` / `;`, plain imperative prose, and multiline continuation;
- conceptual documentation continues to use bare command names when no executable full-form command is intended.

## Identity

- documentation/spec package: `0.35.0-p8-clean-chat-root-guard-hardening`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final frozen-source validation:

- full pytest: **261 passed, 1 skipped, 258 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**, 625 tracked / 625 actual files.

The new adversarial guard cases explicitly prove that rootless commands are detected after `&&`, before `||`, after `;`, and in ordinary unbackticked imperative prose, while a valid backslash-continued command with `--project-root <root>` still passes.

After this record update the manifest is regenerated again, and the final archive is independently unpacked and revalidated before delivery.
