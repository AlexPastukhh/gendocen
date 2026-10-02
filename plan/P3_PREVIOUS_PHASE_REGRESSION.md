# P0–P2 Regression Check After P3 Post-Acceptance Correction

Date: 2026-10-02

Purpose: prove that the P3 state/event correction did not break guarantees already accepted in P0, P1 or P2.

## P0/P1 foundation and resource layer

Command group covers CLI/output/config/project/object/ref/JSON/schema/sample/init/resource tests.

Result:

```text
55 passed, 46 subtests passed
```

Re-exercised guarantees include:

- CLI/machine-output foundation;
- root/config discovery;
- strict JSON parsing;
- canonical refs;
- schema validation;
- immutable raw objects;
- path/symlink confinement;
- idempotent init;
- resource catalog/loading.

## P2 builder and extension layer

Command group covers builders, extension loading and domain-neutrality.

Result:

```text
32 passed, 99 subtests passed
```

Re-exercised guarantees include:

- immutable derived objects;
- exact tracked reads and whole-resource reads;
- derived-of-derived builds;
- deterministic cycle errors;
- project-package loading;
- builder/helper revision provenance;
- per-dependency comparators;
- product/tax domain-neutral fixture.

## P3 dependency layer + spec contracts

Result after the A→B→A correction:

```text
31 passed, 23 subtests passed
```

A later final run includes the complete suite and package audit.

## Conclusion

No P0–P2 functional regression was detected by the phase-specific regression groups. Global release-gate closure remains P8; this document only records the previously accepted guarantees re-exercised after the P3 correction.

## Final post-axis full regression and installed-distribution check

After the receipt re-activation correction and ambiguity-index update, the complete source-checkout suite was re-run:

```text
120 passed, 168 subtests passed
```

`python tools/audit_spec.py` then returned `SPEC AUDIT OK`.

The active `0.1.0.dev7` wheel was installed into a fresh virtual environment with no runtime dependencies. `pip check` passed, `docengine --version` returned `0.1.0.dev7`, and installed `status --json` / `graph --json` succeeded on the sample project.

The active wheel contains the same 16 runtime Python modules as `src/docengine`, byte-for-byte. This confirms the post-axis correction did not exist only in the source checkout.

## Cross-phase conclusion

No confirmed regression was found in previously accepted P0, P1 or P2 behavior after P3 and the A → B → A correction. This does not globally close their DAX axes; it re-exercises the concrete guarantees previously accepted for those phases.
