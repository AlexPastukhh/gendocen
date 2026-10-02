# P2 Independent Review — Final

Date: 2026-10-02
Scope: P2 builders, derived objects, tracked reads, project extension boundary, provenance and transferable package.

## Review rule

This review did not assume existing PASS labels were correct. A point is called a defect only when executable behavior contradicts an accepted contract/axis or creates a concrete correctness/safety/handoff failure. Policy choices and future hardening are listed separately.

## Confirmed problems

All confirmed P2-scope problems found by the independent review are corrected in this package. The detailed R1–R12 record is in `P2_REAUDIT.md`.

The final additional defect found after the interrupted review was **R12**: a whole raw `resource://...` dependency used the physical JSON source hash. Therefore changing only JSON formatting or `$docengine.materialize` metadata changed dependency evidence even though the domain object was identical. This was corrected so:

- `source_hash` remains a physical canonical-source-file fingerprint for inventory/source provenance;
- a whole raw-resource dependency version is the canonical hash of its domain `data`;
- a field dependency version is the canonical hash of the addressed value;
- formatting/envelope-only changes do not create false computational dependency changes;
- domain-data changes still change the dependency version.

Regression coverage is in `tests/test_p1_resources.py`.

## No confirmed remaining P2-scope defect

After the corrections:

- full suite: **93 passed, 149 subtests passed**;
- specification audit: **SPEC AUDIT OK** before and after tests;
- final wheel: `generic_documentation_engine-0.1.0.dev5-py3-none-any.whl`;
- clean-venv installation and `pip check`: PASS;
- installed sample build and unrelated product+tax build: PASS;
- wheel/runtime source parity: enforced by `tools/audit_spec.py`;
- manifest/package integrity: enforced by `tools/audit_spec.py` and final ZIP verification.

This does not close future-phase axes globally; it means no remaining defect was confirmed in the implemented P2 scope.

## Ambiguous / policy-sensitive points — not classified as current defects

### A1 — cooperative tracking rather than sandbox enforcement

Project Python can deliberately bypass `BuildContext` and perform arbitrary I/O. v0.1 explicitly labels provenance `tracking_assurance="cooperative"`; `audit_complete=true` means no known gaps under the context-usage contract, not proof of sandbox isolation.

This is an explicit trust model, not a hidden defect. Stronger isolation can be evaluated in hardening if desired.

### A2 — no project-specific derived-output schema contract yet

P2 validates the generic derived envelope and JSON-compatible output, but does not yet require a schema for each project's derived `data`. Current P2 acceptance did not require one. Whether project-derived outputs should support optional/required schemas is a legitimate later design choice.

### A3 — builder revision is conservative, not per-builder-minimal

`builder_revision` hashes the project package source bundle. This safely detects relevant code changes, but an unrelated Python edit in that package may cause extra `build_required` work in P3. Computing an exact static code/import closure per Python builder is substantially harder and is not required for P2 correctness.

### A4 — object-wrapper infrastructure metadata is diagnostic, not a semantic input

`ctx.get()` returns a `RawObject`/`DerivedObject` wrapper, but the accepted dependency semantics concern the canonical domain value. Documentation now states that wrapper infrastructure fields such as physical source paths or provenance metadata are diagnostic and must not be used as hidden derivation inputs. If such information must affect a result, it should be modeled as explicit structured data/dependency.

This remains part of the cooperative programming contract rather than an enforced restricted view. A future stricter value-view type could enforce it if experience shows that necessary.

## Questions produced by the review

### Blocking user questions

**None.** No unresolved decision is required from the user before P3.

### Optional future policy question

Whether a hardening phase should add stronger isolation/restricted execution for project builder code instead of the current cooperative/trusted model. This does not block P3 and should not be decided prematurely without a concrete need.

## P3 watch items

These are implementation obligations, not new user questions:

- persist `builder_revision` and invalidate deterministic targets when it changes;
- snapshot canonical dependency slices rather than storage envelopes;
- validate comparator ids against the P3 comparator registry;
- keep semantic validity decisions for human/AI review rather than inferring them from a diff;
- preserve the distinction between physical source provenance and semantic dependency versions.
