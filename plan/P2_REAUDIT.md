# P2 Independent Re-Audit

## Method

The accepted P2 package was reviewed without assuming prior `PASS` statuses were correct. Review included:

- source inspection of builders, refs, resource catalog and extension loader;
- adversarial executable probes;
- cross-check against architecture/docs and DAX definitions;
- distinction between confirmed defects and design limitations;
- regression tests for every corrected executable defect.

## Confirmed defects found and corrected

### R1 — internal derived objects were over-structured

Documentation said internal derived objects do not need JSON, but extension loading required a descriptor for every builder target.

**Correction:** internal-only targets may be code-only. Materialized/documentation-owned derived targets continue to use `derived_descriptor`.

### R2 — derived descriptor could become fake raw truth

A descriptor with no builder remained readable through `ResourceCatalog` as raw descriptor `data` (often `{}`).

**Correction:** every `derived_descriptor` must have a registered builder once project extensions are loaded, and the resource API itself rejects reading/versioning descriptor `data` as raw domain truth. Descriptor JSON remains inventory/output metadata only.

### R3 — file ref storage-boundary bypass

`file://_structured/...json` and generated Markdown could be read as plain file dependencies.

**Correction:** in v0.1, `file://` resolves only inventory entries classified as plain canonical Markdown. Managed/derived content uses `resource://`.

### R4 — direct ResourceRef construction bypassed validation

A caller could instantiate an invalid resource namespace and register a builder on a ref whose own string representation could not be parsed back.

**Correction:** `ResourceRef.__post_init__` validates direct construction; textual parsing also rejects non-canonical percent encodings rather than silently normalizing.

### R5 — dotted project-package contract was false

`project_package="company.builders"` passed configuration validation but `from ..common import ...` failed because the leaf was loaded as an artificial top-level package.

**Correction:** package hierarchy is loaded beneath a private synthetic root, preserving normal relative-import semantics without exposing project packages globally.

### R6 — builder-code changes were absent from provenance

Builder id alone does not identify the formula/helper code revision. P3 could otherwise miss code-only derivation changes.

**Correction:** project Python source is content-addressed; derived provenance includes `builder_revision`. P3 acceptance now requires code-revision invalidation.

### R7 — comparator granularity mismatched future receipts

One builder-level comparator was insufficient for builders reading values requiring different comparison semantics.

**Correction:** builder comparator is the default; `ctx.read/get(..., comparator=...)` may override it per dependency, and each dependency evidence entry stores its comparator.

### R8 — stale handoff documentation

`AI_USAGE_PROTOCOL.md` still called the package a P1 boundary after P2 acceptance.

**Correction:** updated to current P2 capabilities and P3 next phase.

### R9 — incorrect file-ref examples

`DEPENDENCY_MODEL.md` used `file://docs/...` although file refs are relative to documentation root.

**Correction:** examples use `file://architecture/...` / `file://policies/...`.

### R10 — dotted child package could execute twice

If a parent package `__init__.py` imported the configured dotted child package, the extension loader then executed that already-imported child a second time. This violated the documented Python package semantics and could duplicate import side effects.

**Correction:** the loader now reuses an already-loaded expected child module under the private synthetic package root after verifying its source path, rather than executing it twice.

### R11 — active handoff identity could lag the re-audited runtime

After the re-audit code advanced to dev4, active README/START/package-audit text still named the prior dev3 distribution. Historical dev3 evidence is legitimate history, but active handoff documentation must identify the current build.

**Correction:** the intermediate re-audit advanced active handoff docs to package v0.11 / runtime dev4; the final correction advances them again to package v0.12 / runtime dev5; self-audit now checks current runtime identity in active handoff docs while retaining historical evidence unchanged.

### R12 — whole-resource dependency used physical JSON identity

A whole raw `resource://...` dependency initially used the physical JSON source hash. Formatting-only or `$docengine` metadata changes could therefore change dependency evidence even when canonical domain `data` was unchanged.

**Correction:** `source_hash` remains physical source provenance, while whole structured-resource dependency version is the canonical hash of domain `data`; field dependency version remains the canonical hash of the addressed field value.

## Ambiguous / policy-sensitive points

### A1 — cooperative tracking vs sandboxing

Direct Python I/O cannot be observed reliably without isolation. The v0.1 design remains cooperative/trusted and now exposes `tracking_assurance="cooperative"`. This is acceptable for the current architecture but is not equivalent to sandbox-enforced completeness.

### A2 — derived domain-output schema

Generic envelope validation exists; a separate project output-schema contract for built data does not. This is not required by current P2 acceptance, so it is left as a future design decision rather than fabricated as a defect.

### A3 — builder source-revision granularity

The v0.1 project loader hashes the whole top-level project Python package, so a change in unrelated project Python can conservatively change `builder_revision` for every registered builder. This is safe for correctness but may cause extra rebuilds. It is not a P2 correctness defect; P3 should keep the conservative behavior explicit and finer per-builder/helper provenance can be a later optimization.


### A4 — object-wrapper metadata semantics

`ctx.get()` returns object wrappers that also expose infrastructure metadata. The accepted v0.1 contract treats canonical domain data as the semantic dependency; wrapper source/provenance metadata is diagnostic and must not be used as a hidden derivation input. This is currently enforced by the cooperative programming contract rather than a restricted value-view type.

## New user questions

No blocking user question was discovered by this audit. The audit did expose implementation/design questions that are recorded for the relevant later phase: P3 must preserve the now-defined domain-data whole-resource baseline semantics and consume code revision conservatively; a later hardening phase may optionally evaluate stronger isolation for project builder code. None requires a user answer before P3 starts because safe defaults are recorded.
