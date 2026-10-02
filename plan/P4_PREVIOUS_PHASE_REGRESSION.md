# P0–P3 Regression Check During P4

Date: 2026-10-02

Purpose: demonstrate that P4 semantic-review changes did not silently break previously accepted P0–P3 behavior.

## Functional regression before package gate

The complete functional suite excluding only package-audit/hygiene checks passed after P4 implementation and cross-phase corrections:

```text
139 passed, 175 subtests passed
```

This included the P3 missing-target diagnostic regression that exposed and then verified the correction to semantic extension loading.

## Cross-phase conclusion

No confirmed P0–P3 functional regression remains after the P4 corrections. This document does not globally close earlier DAX axes; it re-exercises their implemented guarantees before P4 handoff.

Final full-suite and installed-wheel counts are appended after the frozen package gate.

## Final full-suite confirmation

After P4 acceptance corrections and package-hygiene synchronization, the complete source checkout passed:

```text
141 passed, 175 subtests passed
```

`tools/audit_spec.py` returned `SPEC AUDIT OK` after the suite and after `compileall`. The dev8 wheel installed cleanly and contains the same 17 runtime Python modules as `src/docengine`.
