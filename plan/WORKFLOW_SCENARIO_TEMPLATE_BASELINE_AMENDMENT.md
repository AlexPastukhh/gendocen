# Workflow scenario-template baseline amendment — v0.36

## Status

Additive refinement only. The historical pre-work baseline remains unchanged and continues to document the requirement that existed when the documentation/workflow unit began.

## Trigger

Independent final review found that the original Phase-4 wording, “use one consistent scenario template,” had been interpreted as requiring identical headings such as `Starting state`, `Journey`, and `Outcome` in every WF01–WF12. The underlying goal was valid — workflows must be real operational scenarios rather than a reformatted CLI catalog — but identical headings add artificial verbosity to compact inspection/recovery/migration workflows without improving correctness.

## Refined requirement effective for v0.36+

Every core workflow must state, unambiguously:

1. **Actor**;
2. **Goal**;
3. **Atomic contract(s)**;
4. **Operational path** — what the actor actually does / what transition is followed;
5. **Observable result** — the state/output/evidence the actor should see.

Additional headings such as `Starting state`, `Journey`, `Outcome`, `Problem`, `Review flow`, `Typical flow`, or `Normal flow` are used when they materially improve comprehension. Complex authoring/review workflows (especially WF03–WF05) remain richer end-to-end journeys. Inspection and hardening workflows may stay compact when the semantic minimum is explicit.

## Relationship to EA-11

EA-11 remains valid: workflows must not collapse into one-command-per-use-case lists without actor/goal/observable behavior. The acceptance criterion is refined from identical heading names to the semantic minimum above. This amendment does not weaken any engine behavior, atomic DOCxx contract, ownership rule, trust boundary, or runnable-example requirement.

## Verification

`tests/test_documentation_workflows.py` asserts Actor, Goal, Atomic contract(s), Operational path, and Observable result for every WF01–WF12.
