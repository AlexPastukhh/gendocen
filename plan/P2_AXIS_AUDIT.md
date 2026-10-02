# P2 DAX Audit — independent re-audit

Date: 2026-10-02
Decision: **PASS for P2 risk slice after corrections**. Global axis closure remains P8.

| Axis | P2 result | Evidence / boundary |
|---|---|---|
| DAX02 Documentation ownership/layout | PASS | Materialized derived outputs remain documentation-owned through `_structured`; internal-only derived targets do not force JSON; existing descriptors require builders. |
| DAX03 Identity/schema/version integrity | PASS | Direct and textual refs are canonical; dotted package contract works; provenance schema includes builder revision; runtime build advanced to dev5. |
| DAX04 Path/data safety | PASS | Project package confined/symlink-safe; `file://` cannot access reserved structured/runtime storage or generated managed views; P2 persists no runtime state. |
| DAX05 Raw/derived separation/provenance | PASS | Raw objects stay immutable; derived descriptors never become raw fallback values; derived outputs carry deterministic provenance plus code revision. |
| DAX06 Dependency capture/granularity | PASS WITH EXPLICIT COOPERATIVE BOUNDARY | Exact refs and per-dependency comparators are captured; whole raw resources version canonical domain data rather than storage envelope bytes; plain-file boundary enforced; direct arbitrary Python I/O remains outside the cooperative tracking contract and is explicitly identified as such. |
| DAX10 Determinism/idempotency | PASS | Stable dependency ordering/digests and source revision; same code+inputs reproduce equivalent output/provenance. |
| DAX14 Diagnostics/repairability | PASS for introduced slice | Builder failures identify target/builder; cycles expose exact paths. Persistent history/repair remains P3/P7. |
| DAX17 Domain independence/extensibility | PASS | Product/tax fixture uses same core; dotted project packages retain normal relative-import semantics under isolated prefix. |
| DAX19 Test assurance | PASS | Positive/negative, mutation, chain, cycle, canonical-ref, storage-boundary, descriptor symmetry, nested-package, code-revision and comparator tests. |
| DAX20 Release/handoff integrity | PASS | Docs updated to P2 boundary; active dev5 wheel/source parity, manifest and clean archive are final gates. |

## Not promoted to defects

### Cooperative Python tracking

The runtime cannot prove that arbitrary Python avoided direct filesystem/network access. This is a real limitation of the trust model, but not an implementation contradiction once the assurance is stated explicitly. P2 therefore reports `tracking_assurance="cooperative"`; sandboxing is not claimed.

### Domain-specific output schema for derived data

P2 validates the generic derived envelope and JSON compatibility, but does not yet define a separate project `output_schema` contract for builder results. No current P2 acceptance criterion promises this, so it is not classified as a P2 defect. It can be added later if needed before renderer/materialization contracts depend on typed derived output.

## Pre-P3 correction carried forward

P3 now has an explicit acceptance criterion requiring a builder/helper source revision change to produce `build_required` even when data dependencies are unchanged. P2 provides the source revision needed for that check.

## Additional verified findings from independent re-audit

- **DAX05:** descriptor-as-raw fallback is closed at the ResourceCatalog API itself, not only during project-extension validation.
- **DAX10 / DAX17:** a dotted child imported by its parent is executed once; repeated loader execution is prevented after verifying the existing module source path.
- **DAX20:** active README/START/package audit must identify the current runtime build; historical evidence may retain its original dev3 identity.

## Deliberately not classified as P2 defects

- **Cooperative tracking:** arbitrary project Python can bypass `BuildContext`; v0.1 explicitly reports `tracking_assurance=cooperative`. This is a trust/sandbox policy boundary, not a hidden guarantee.
- **Project-derived output schema:** generic envelope validation exists, but project-specific schema validation of builder output is not part of current P2 acceptance.
- **Code revision granularity:** project Python revision is package-wide and conservative. This can over-invalidate but does not miss project-package Python changes; finer granularity is an optimization.
- **Whole structured-resource baseline semantics:** this becomes a P3 persistence/diff decision. P3 records now define the v0.1 baseline as domain `data`, not unrelated `$docengine` metadata.
