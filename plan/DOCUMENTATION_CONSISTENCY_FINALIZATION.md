# Documentation consistency finalization — v0.36

## Scope

Documentation/test/release-evidence correction on top of v0.35. Runtime semantics remain `0.1.0.dev20`; `src/docengine/**` is unchanged.

## Trigger

Independent full-package review found four non-runtime cleanup items:

1. active package identity was v0.35 while README/handoff/navigation metadata still named v0.32–v0.34 in current-state positions;
2. the generic WF03 example used multiplication even though baseline WR-11 explicitly required `A.field3 + B.field2`;
3. the historical Phase-4 identical-heading scenario-template wording was stricter than needed for compact inspection/hardening workflows, although the real-scenario goal remained valid;
4. the v0.35 root guard recognized the substring `--project-root`, allowing a shell comment or quoted argument value to masquerade as the actual CLI option.

## Corrections

- current README/maintainer/repository/system/file-map identity is synchronized through v0.36;
- WF03 restores the exact baseline addition example while the product-tax fixture remains a separate realistic multiplication/tax scenario;
- `plan/WORKFLOW_SCENARIO_TEMPLATE_BASELINE_AMENDMENT.md` records an additive semantic-minimum refinement without rewriting the historical baseline, and every WF now states Operational path + Observable result explicitly;
- the zero-context root guard tokenizes each command segment with shell-comment/quote awareness and recognizes `--project-root` only as an actual option token (`--project-root VALUE` or `--project-root=VALUE`), not inside comments or quoted values;
- regressions cover active identity, exact WF03 arithmetic, workflow semantic minimum, shell-comment masking, quoted-value masking, compound commands and valid multiline explicit-root commands.

## Identity

- documentation/spec package: `0.36.0-p8-documentation-consistency-finalization`;
- runtime build: `0.1.0.dev20` unchanged;
- engine phase: P8 accepted, no P9.

## Validation

Final frozen-source validation:

- full pytest: **267 passed, 1 skipped, 270 subtests passed**;
- `python tools/audit_spec.py`: **PASS**;
- `python tools/audit_axes.py --json`: **PASS**, no findings;
- `python tools/release_check.py --json`: **PASS**, no findings;
- `python tools/benchmark_release.py --json`: **PASS**, 10,000 targets / 50,000 edges within budget;
- `python tools/release_manifest.py validate --json`: **PASS**, 627 tracked / 627 actual files.

The manifest is regenerated after this record update. The final archive is then independently unpacked and revalidated before delivery.
