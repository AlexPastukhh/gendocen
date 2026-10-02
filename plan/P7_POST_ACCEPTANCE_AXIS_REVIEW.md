# P7 Post-Acceptance Axis Review

Date: 2026-10-02
Decision: **PASS after corrections for DAX14/DAX15/DAX16/DAX20; DAX18 remains explicit partial**
Runtime corrected/final P7 build: **0.1.0.dev15**
Package correction candidate: **0.23.0-p7-postaxis-audited-final**

## Method

This review did not trust the prior P7 PASS labels. Transaction/recovery/migration behavior was probed with malformed journals, rogue transaction entries, rollback failures, post-crash external deletion, corrupt/symlinked released migration evidence, forged migration provenance, corrupt receipts and corrupt hardening audit logs. A finding is called a defect only when executable behavior contradicted an accepted P6/P7 contract.

## Confirmed defects found and corrected

### R1 — Semantically impossible journal could be destructive

A schema-shaped open journal claiming a pre-existing file was transaction-created (`existed=false`) could instruct recovery to delete the real file.

**Correction:** recovery now validates full journal semantics before the first mutation. Current filesystem/pre-image relationships, transaction-directory identity and operation invariants must be coherent. Corrupt evidence remains preserved and `recovery_required`.

**Axes:** DAX14, DAX15.

### R2 — Failed synchronous rollback could destroy recovery evidence

If rollback itself failed (for example a missing pre-image backup), transaction cleanup could remove the journal/pre-images even though the target remained mutated.

**Correction:** failed rollback preserves the transaction directory and evidence so a later `recover`/diagnostic can see the unresolved state. It never claims rollback success.

**Axes:** DAX14, DAX15.

### R3 — Rogue transaction-root entries could be silently ignored

Unexpected files/symlinks under the transaction namespace were not necessarily treated as corruption.

**Correction:** every unexpected transaction-root entry is a blocking recovery condition. No mutation proceeds until resolved.

**Axes:** DAX04, DAX14, DAX15.

### R4 — External deletion after crash was not treated as a conflict

The existing conflict guard protected unknown current bytes but not disappearance of a file that existed before the interrupted transaction. Normal recovery could recreate it, overwriting an external decision.

**Correction:** missing-vs-preexisting is a conflict too. Default recovery refuses; explicit `recover --force` restores the pre-crash file and records `forced=true` plus the conflict path.

**Axes:** DAX14, DAX15.

### R5 — Runtime-layout schema/provenance could disagree with runtime trust

The published marker schema/runtime checks did not fully encode the same provenance rules, and a marker could self-assert unknown `migrated_from`/`migration_id` values.

**Correction:** marker parsing matches schema-critical shape and migrated provenance must correspond to the registered migration path. Unknown/self-declared provenance is invalid.

**Axis:** DAX16.

### R6 — Migration could accept unsafe/corrupt released evidence

A legacy receipt represented by a symlink, or integrity-corrupt released evidence, could be omitted/misinterpreted by preservation scanning and still receive a current layout marker.

**Correction:** migration validates released evidence paths/types/integrity first, refuses symlinked/tampered evidence, and writes no current marker on failure.

**Axes:** DAX04, DAX16.

### R7 — Corrupt persisted evidence could break P6 complete-report verify

A corrupt dependency receipt could escape as internal error instead of returning a normal blocking verification report.

**Correction:** verification contains store/integrity failures as findings (`receipt_store_invalid`/`active_receipts_unreadable` etc.) and keeps the report envelope.

**Axes:** DAX14, DAX20; preserves accepted P6 verify semantics.

### R8 — Hardening audit-log corruption was not release-verified

Migration/recovery events are claimed as audit evidence, but malformed audit JSONL could be omitted from verify findings.

**Correction:** verify validates hardening migration/recovery audit logs and reports corruption as blocking evidence while continuing the rest of the report.

**Axis:** DAX14.

### R9 — Transaction-id mismatch could become path-selection authority

A journal whose internal `transaction_id` differed from its directory identity had ambiguous authority.

**Correction:** this is corruption, not a selectable transaction. Recovery refuses and preserves evidence.

**Axes:** DAX14, DAX15.

### R10 — Accepted P7 handoff contained stale P6-era documentation strings

Active docs/source help still contained earlier-phase wording such as “Implemented through P6”/old runtime identity after P7 acceptance.

**Correction:** active P7 docs and CLI/source README are synchronized to P7/dev15 and `audit_spec.py` gains guards so the mismatch cannot silently recur.

**Axis:** DAX20.

## Axis result after correction

| Axis | Post-axis result | Conclusion |
|---|---|---|
| DAX04 Path confinement/data safety | PASS for corrected P7 slice | rogue/symlinked transaction/migration evidence is rejected; migration never follows unsafe released evidence. |
| DAX14 History/provenance/diagnostics | PASS after R1–R9 | corrupt recovery/migration evidence is fail-closed, preserved, and visible in complete-report verification. |
| DAX15 Crash/retry/concurrency/transactional integrity | PASS after R1–R4/R9 | rollback authority is fully validated before mutation; failed rollback preserves evidence; external deletion is conflict. |
| DAX16 Migration/backward compatibility | PASS after R5/R6 | migration provenance is registry-bound and released evidence must validate before a current marker is written. |
| DAX18 Performance/scalability | **PARTIAL unchanged** | P7 baseline remains measured; normalized release budget remains mandatory P8-A8. |
| DAX19 Test assurance | PASS | new post-axis regressions cover every reproduced defect plus full P0–P7 regression. |
| DAX20 Handoff integrity | PASS | dev15 corrected docs/source, clean-installed post-axis scenarios, final manifest-only portable copy and ZIP gate pass. |

## Ambiguous / policy-sensitive points

No new unresolved user-facing ambiguity was discovered.

Existing **A1** remains: project Python is trusted/cooperative and not sandboxed. This review does not reclassify that explicit boundary as a P7 defect.

DAX18 remained deliberately partial under Q7.3/Q7.E8 at P7 acceptance and is represented by P7-CG1; P8-A8 subsequently resolved it before final release.

## Questions produced by this review

No new user-owned question appeared.

Three implementer-owned questions were made explicit and resolved:

- **Q7.E9:** may a corrupt/semantically impossible journal be executed? → **No; fail closed before any mutation.**
- **Q7.E10:** is migration marker provenance self-authenticating? → **No; it must match a registered migration and validated released evidence.**
- **Q7.E11:** are migration/recovery logs verification evidence? → **Yes; corruption is a blocking verify finding.**

No unresolved blocking question remains before P8. DAX18/P8-A8 is a release criterion, not an unanswered question.

## Evidence

- `tests/test_p7_hardening.py::P7PostAxisRegressionTests`
- `src/docengine/hardening.py`
- `src/docengine/verification.py`
- `spec/schemas/TRANSACTION_JOURNAL.schema.json`
- `spec/schemas/RUNTIME_LAYOUT.schema.json`
- `spec/schemas/HARDENING_MIGRATION_EVENT.schema.json`
- `spec/schemas/HARDENING_RECOVERY_EVENT.schema.json`

Final distribution evidence is recorded in `P7_PACKAGE_AUDIT.md`; the dev15 package gate passed.
