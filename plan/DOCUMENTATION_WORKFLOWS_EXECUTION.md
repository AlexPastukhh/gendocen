# Documentation / Core Workflows execution record — v0.29

## Scope

This is a post-P8 documentation/spec normalization. Runtime semantics are unchanged. Historical accepted phase records/evidence are preserved; current missing use-case coverage is additive via `USE_CASE_COVERAGE_AMENDMENTS.json`.

## Baseline verification

Before edits:

- full pytest: 232 passed, 1 skipped, 253 subtests passed;
- `tools/audit_spec.py`: PASS;
- atomic registry: DOC01–DOC22, with DOC18/DOC19 future;
- public CLI also contained `recover` and `migrate` without dedicated atomic use cases.

## Historical evidence policy resolution

`docs/REPOSITORY_WORKFLOW.md` says historical evidence is append-only for practical repository use, and phase acceptance docs explicitly preserve historical status instead of retroactively rewriting it. Therefore P7 execution records were **not** rewritten. DOC23/DOC24 use additive current coverage amendments pointing to existing P7 evidence.

## DOC01–DOC22 audit matrix

| UC | Result | Action |
|---|---|---|
| DOC01 | OK | none |
| DOC02 | OK | workflow/ownership explanation added |
| DOC03 | unclear/conflated | clarified deterministic tracked reads vs explicit semantic rules |
| DOC04 | OK | referenced by WF02/WF03 |
| DOC05 | incorrect persistence wording | removed canonical derived-object-store implication |
| DOC06 | OK | presentation boundary clarified |
| DOC07 | high-level state wording too broad | exact build_required/review_required/stale mapping added |
| DOC08 | OK | diagnostics workflow |
| DOC09 | OK | diagnostics/review workflow |
| DOC10 | OK | diagnostics/review workflow |
| DOC11 | incorrect persistence/materialization wording | receipt/baseline/state evidence separated from transient object and materialization |
| DOC12 | OK | semantic workflow |
| DOC13 | OK | semantic workflow |
| DOC14 | OK | semantic workflow |
| DOC15 | correct but underspecified | selective rebuild and `--all` materialization semantics clarified |
| DOC16 | read-only caveat missing | clarified engine-state read-only vs trusted unsandboxed project callbacks |
| DOC17 | OK | diagnostics workflow |
| DOC18 | future | kept future; future workflow only |
| DOC19 | future | kept future; future workflow only |
| DOC20 | OK | diagnostics/derived workflow |
| DOC21 | OK | ownership-discovery workflow |
| DOC22 | OK | reproducibility workflow |

## Added atomic use cases

- DOC23 — Recover interrupted transaction (already-implemented P7 capability).
- DOC24 — Migrate runtime layout (already-implemented P7 capability).

## Authoring architecture decisions

Accepted target-oriented mirrored convention:

```text
docs/<logical/path>.md
docs/_structured/<logical/path>.json
docengine_project/builders/<logical/path>.py
docengine_project/dependency_rules/<logical/path>.py
```

Placement and registration are separate: nested modules must be imported/registered through the root project extension surface.

Safe-practice boundary is organizational/cooperative, not a sandbox. Ordinary project authoring does not need `src/docengine/**` edits.

## Execution-discovered documentation defects / baseline deltas

The pre-work goal did not change, but two additional stale documentation facts were discovered while executing the planned consistency sweep:

1. `docs/MATERIALIZATION_RUNTIME.md` still described the pre-P6 `attention_required` sync exit as `0`; current machine contract is exit `2`.
2. The same file's "current CLI boundary" omitted the already-implemented P7 `recover` and `migrate` commands.

Both are documentation-only corrections consistent with accepted runtime behavior. The historical-evidence question was resolved through the existing append-only policy and required no change to the work objective.

## Fixture/test compatibility correction during execution

The accepted mirrored authoring layout changed the project-package source revision and made the bundled product example current after synchronization. One legacy-compatibility regression test had previously depended on that example accidentally remaining in a pre-state-revision format. The test was corrected to construct the legacy representation explicitly (legacy state without `state_revision` plus a matching legacy event/receipt) before exercising upgrade-on-change. Runtime semantics were not changed.

Historical flat project files referenced by accepted phase evidence/tests were retained as compatibility/registration indexes. Active default builder/rule logic lives in the mirrored modules.

## Final validation results

After the documentation/spec/example/test changes and fixture synchronization:

- full pytest: **243 passed, 1 skipped, 255 subtests passed**;
- `python tools/audit_spec.py`: **PASS** (`v0.1_use_cases=22`);
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**; 10,000 targets / 50,000 edges, normalized total ratio within budget;
- `python tools/release_manifest.py validate`: **PASS**.

## Runtime scope confirmation

No gendocen core runtime semantics were intentionally changed in this unit. Runtime version remains `0.1.0.dev20`. The package/documentation identity is `0.29.0-p8-documentation-workflows-correction`.

## Baseline changes recorded during execution

No user-goal or runtime-scope change occurred. The only execution-discovered documentation corrections were the stale `MATERIALIZATION_RUNTIME.md` exit-code/CLI-boundary statements recorded above. The historical-evidence policy was resolved before DOC23/DOC24 provenance normalization, using an additive amendment registry rather than rewriting accepted P7 records.
