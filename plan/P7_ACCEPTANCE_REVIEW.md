# P7 Acceptance Review — Hardening, recovery, migrations and scalability

Date: 2026-10-02
Decision: **ACCEPTED (historical P7 scope)**
Runtime build at P7 finalization: **0.1.0.dev15**
Next phase at that time: **P8 — Final verification and handoff**

## Final P7 scope result

P7 provides external locking, durable multi-file transaction journals, crash recovery, recovery audit history, runtime-layout migrations and the declared scalability baseline while preserving P0–P6 semantics.

| Criterion | Final P7 result | Final interpretation |
|---|---|---|
| P7-A1 crash consistency | PASS | strict journal parsing/preflight; rollback failures preserve evidence; external deletion is a conflict |
| P7-A2 concurrent writer/reader boundary | PASS | external shared/exclusive lock semantics pass on the POSIX acceptance environment |
| P7-A3 migration/version integrity | PASS | corrupt/symlinked legacy evidence rejected; marker cross-links migration registry + event |
| P7-A4 auditable recovery | PASS | migration/recovery event logs are strict verification evidence |
| P7-A5 synthetic scale/budget | **PARTIAL at P7 acceptance** | explicitly carried by `P7-CG1` to P8-A8/DAX18; P8 subsequently resolved the gate |
| P7-A6 earlier semantics + package handoff | PASS | final dev15 wheel/manifest/portable package gate passed |

## Post-axis corrections

The original v0.22/dev14 P7 package had real recovery/provenance defects. The dev15 post-axis correction fixed them and added targeted regressions; canonical details are in `P7_POST_ACCEPTANCE_AXIS_REVIEW.md`.

## Platform locking support matrix

- POSIX: concurrent readers use shared `fcntl` locks; writers are exclusive.
- Windows fallback: access is safely serialized with `msvcrt`; concurrent-reader parity is **not** a v0.1 requirement.

P8 closed the former A7 portability watch item by accepting safe Windows serialization as the v0.1 support contract. Shared-reader parity on Windows is a post-v0.1 enhancement, not an unresolved release question.

## Carried release gate

P7 did not retroactively claim DAX18 PASS. `P7-A5` and P7/DAX18 remain historically `partial`; canonical `P7-CG1` records the carry to P8-A8. P8 established the normalized budget and passed DAX18 before final release.
