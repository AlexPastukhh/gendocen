# P8 Post-Acceptance Consistency Review

Date: 2026-10-02
Correction line: **v0.25 / runtime 0.1.0.dev17**
Decision: **PASS after consistency corrections and v0.25 distribution gate**

## Method

The review re-ran all release gates from the v0.24 source archive and independently cross-checked phase records, DAX registry semantics, historical evidence references, release tooling, handoff documents and top-level ambiguity status. Existing `PASS` labels were not treated as proof.

## Confirmed defects reproduced in v0.24

### C1 — Documented DAX18 benchmark command was not self-contained

`python tools/benchmark_release.py --json` failed from the clean source archive because its subprocess invoked `tools/benchmark_p7.py` without making `src/` importable. The benchmark itself passed when the caller manually supplied `PYTHONPATH=src`, so this was a reproducibility/tooling defect rather than a performance regression.

**Correction:** `benchmark_release.py` now injects `<root>/src` into the subprocess environment while preserving any existing `PYTHONPATH`. A clean-source subprocess regression removes caller `PYTHONPATH` explicitly and must still pass.

**Axes:** DAX18 evidence reproducibility, DAX19 assurance, DAX20 handoff.

### C2 — P7 historical handoff documents remained in pre-final candidate state

The final P8 archive contained an accepted P7 execution record while `P7_ACCEPTANCE_REVIEW.md`, `P7_AXIS_AUDIT.md` and `IMPLEMENTATION_PLAN.md` still described a pending package gate/acceptance review. P7/DAX20 findings also retained stale pending sentences.

**Correction:** P7 historical documents now state final dev15 package PASS. P7-A5/DAX18 remains historically partial and is not retroactively rewritten; its later resolution is represented explicitly by `P7-CG1 → P8-A8`.

**Axis:** DAX20.

### C3 — Top-level ambiguity index was not in final-release state

`OPEN_QUESTIONS_AND_AMBIGUITIES.md` still said there were no blockers “before P7”, described DAX18 as a future P8 obligation after P8 had already passed it, and left Windows shared-reader parity as a “P8 clarification” watch item.

**Correction:** final-release blocking state is explicit; DAX18 is recorded as resolved by P8; A7 is closed as a v0.1 support contract: POSIX shared readers, safe serialized Windows fallback, no Windows concurrent-reader parity guarantee in v0.1.

**Axis:** DAX20.

### C4 — Declared phase acceptance rule contradicted accepted P7 history

The registry said every criterion/axis must pass for phase acceptance, while P7 was intentionally accepted with P7-A5/DAX18 partial and carried into P8 by Q7.E8. The global auditor implicitly allowed this without a formal model.

**Correction:** phase records now support canonical `carried_release_gates`. A partial criterion/axis is legal in an accepted phase only when the exact source criterion/axis is carried to a concrete later target criterion. Final release rejects any open carry. `P7-CG1` is resolved only because P8-A8 and P8/DAX18 pass.

**Axes:** DAX03 process/schema integrity, DAX19 assurance, DAX20 handoff.

### C5 — Historical P1/P2 evidence references pointed to deleted active-dist wheels

P1/P2 phase records referenced old `dist/*.whl` paths that no longer exist because active `dist/` correctly contains only the current wheel.

**Correction:** those references now point to retained historical package evidence (`clean_venv_install.txt` for P1 dev2 and `wheel_sha256.txt` for P2 dev5). Global axis audit validates path-like evidence-reference resolvability.

**Axes:** DAX14 provenance/referential integrity, DAX20.

### C6 — Assurance did not exercise the above consistency contracts

The v0.24 suite could pass while the documented benchmark command failed and while historical status/evidence references drifted.

**Correction:** release tests now include clean-source benchmark invocation, carried-gate enforcement and missing evidence-ref detection. `audit_spec.py` imports the canonical axis auditor and rejects stale P7/P8 handoff phrases after P8 acceptance.

**Axes:** DAX19, DAX20.

## Ambiguous / policy-sensitive points

No new unresolved product ambiguity was created.

- A1 trusted/cooperative project Python remains an explicit post-v0.1 boundary.
- A7 is no longer open: safe Windows serialization is accepted for v0.1; shared-reader concurrency parity is post-v0.1.
- P7 historical DAX18 partial is not an ambiguity; it is a resolved carried release gate.

## Questions

No user-owned question appeared.

Two implementer-owned decisions were made explicit:

- **Q8.E3:** close Windows lock parity by accepting safe serialized Windows behavior for v0.1.
- **Q8.E4:** formalize phase-local partial carry using `carried_release_gates`; final release requires resolution.

## Final proof requirements

Before v0.25 handoff:

1. full source suite and self-audit;
2. documented benchmark command from clean source with no caller `PYTHONPATH` requirement;
3. global axis audit with zero findings, including evidence-ref and carried-gate checks;
4. release-manifest validation;
5. clean-installed dev17 lifecycle and wheel/source parity;
6. manifest-only portable copy + exact ZIP member/CRC gate.


## Candidate portable proof completed

The corrected candidate passed the full source suite/self-audit, clean-source benchmark without caller `PYTHONPATH`, dev17 clean-venv lifecycle/wheel parity and a manifest-only portable copy. Final immutable manifest/ZIP freeze repeats these checks after this report is frozen.
