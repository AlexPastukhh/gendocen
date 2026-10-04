# Documentation / Core Workflows independent-review correction — v0.30

## Scope

This is an additive correction after the independent review of the v0.29 documentation/workflow unit. Core runtime semantics remain unchanged (`0.1.0.dev20`). The v0.29 execution record remains historical evidence and is not rewritten.

## Review findings corrected

1. **Semantic mirror authority** — `examples/sample_project/docengine_project/semantic_rules.py` is now a pure forwarding registration index. Rule sources/comparator/type/id live only in `dependency_rules/architecture/rationale.py`. Existing semantic mutation tests now mutate the authoritative mirrored rule.
2. **Ownership discovery** — `resources` distinguishes managed/derived ownership, but a plain file requires `graph file://...` to determine whether a semantic rule applies. Core workflows, architecture, sample tutorial, and AI protocol now teach this two-step classification.
3. **Registration proof** — `resources` is explicitly inventory only. New builder/rule registration is confirmed by `sync`/`rebuild`, or by `graph` with empty `runtime_diagnostics`. The negative registration test proves that an unregistered derived descriptor can appear in `resources` while `sync` fails.
4. **Runnable semantic-change tutorial** — the sample walkthrough first establishes and validates an initial semantic baseline, then mutates `allowed_methods`, and only then expects `dependency_changed`/`review_required`.
5. **Cross-document onboarding consistency** — `REPOSITORY_WORKFLOW.md` now sends learn/use sessions to `README.md` → `CORE_WORKFLOWS.md`; `START_HERE_AGENT.md` remains the maintainer/release route.
6. **Future helper guard** — documentation tests now reject `docengine promote` / `docengine demote` if they appear in the current (pre-future) workflow section.

## Added independent regression coverage

- mirrored semantic rule is authoritative when edited;
- `resources` reports semantic Markdown as plain while `graph` exposes its semantic rule;
- unregistered mirrored builder can appear in inventory but fails an operation that loads/uses builders;
- semantic tutorial produces `initial_validation_required`, validates baseline, then produces `dependency_changed` after mutation;
- repository workflow preserves product-first onboarding;
- current workflows cannot advertise future promote/demote commands.

## Package identity

- documentation/spec package: `0.30.0-p8-documentation-workflows-review-correction`;
- runtime build: `0.1.0.dev20`;
- target stable runtime: `0.1.0`;
- implementation phase remains `P8 accepted`.

## Validation

After the v0.30 correction:

- full pytest: **247 passed, 1 skipped, 255 subtests passed**;
- `python tools/audit_spec.py`: **PASS** (`v0.1_use_cases=22`);
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**;
- adversarial future-helper mutation (`docengine promote` inserted before the Future section) is rejected by the documentation workflow guard;
- no `src/docengine/**` runtime file was changed by this correction.

