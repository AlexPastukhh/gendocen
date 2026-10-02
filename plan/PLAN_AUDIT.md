# Plan Audit — v0.3 correction

This revision was produced by checking the v0.2 plan package against its own schemas/contracts and the conversation decisions.

## Defects found and corrected

1. Sample `dependency_state.json` failed its own schema (`generated_at: null`). Schema now explicitly permits an ungenerated/empty state (`null`) and date-time strings.
2. Dependency state vocabulary conflicted: plan used `build_required`, schema used `rebuild_required`. Canonical machine state is now `build_required`; `rebuild` is the action/command.
3. P2/P3/P5/P7(old release) criteria referenced DAX axes not declared by the phase. Phase mappings were corrected.
4. Release sequencing was invalid: final release preceded hardening even though DAX15 (crash/concurrency/transactional integrity) is a release gate. Hardening is now P7; final release is P8.
5. Final release did not consolidate every global release-gate axis. P8 now maps/reviews all release-gate axes.
6. DOC18/DOC19/DOC21 were not consistently represented in implementation coverage. DOC21 is mapped to v0.1; DOC18/DOC19 are explicitly future rather than silently uncovered.
7. Use-case `cli_surface` and CLI registry could disagree. Use cases now contain machine-checkable `cli_commands`; dependency-rule authoring is explicitly code-level, not a runtime JSON-registration CLI. `init` is added to v0.1 CLI.
8. Several technical choices had been recorded as if they were user answers. Root discovery, mandatory review reason, and exact read-only command boundaries are now implementer-owned decisions.
9. Fully-derived Markdown had no guaranteed JSON location for its output path. A materialized derived resource now uses a documentation-owned `derived_descriptor` JSON under `_structured`; builder/dependency logic remains code.
10. Phase `axis_reviews` existed conceptually but were empty. Every phase record now contains pending review slots for all mapped axes.
11. Version identity was ambiguous. Package version and target runtime version are now explicitly separated.

## Remaining user decisions

- P4/Q4.3 resolved by user: no Markdown section-level dependency addressing in v0.1; use structured JSON for partial-document dependency granularity.
- P8/Q8.1 resolved by user: verify always returns a complete report; blocking findings yield `ok=false` and non-zero exit code rather than a crash.

## Verification

Run `python tools/audit_spec.py`. The package should not be handed off as canonical if this command fails.

## P0 post-acceptance axis audit — v0.6

12. Clarified that a phase-local DAX `PASS` covers only the risk slice introduced/exercised by that phase; it does not globally close the axis. P8 remains the consolidated global release-gate review.
13. Found and fixed a DAX20 reproducibility defect: test-created `.pytest_cache` / `__pycache__` / bytecode files caused false manifest mismatches. Manifest audit now ignores only an explicit transient set and has regression coverage.
