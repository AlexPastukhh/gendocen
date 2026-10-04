# GitHub Checkout Portability Audit — v0.28

Date: 2026-10-03
Status: **ACCEPTANCE CANDIDATE — local/package gates pass; GitHub fresh-checkout CI pending**
Runtime distribution at this v0.28 audit: **0.1.0.dev20**. Current archive runtime after the additive v0.39 project-config root-policy documentation sync: **0.1.0.dev22**
Specification/runtime package: **0.28.0-p8-git-checkout-portability-candidate**

This is a post-P8 repository/runtime bugfix correction, not P9. It introduces no new product semantics and requires no user-owned decision.

## Trigger

The first real push of v0.27 to GitHub produced failing Ubuntu and Windows CI even though the local Windows gate had passed. Inspection of the exact GitHub checkout separated two deterministic repository/runtime defects from unrelated policy questions.

## G1 — manifest frozen before Git EOL normalization

`plan/evidence/windows_portability/windows_real_host_gate_full.txt` entered the release tree with CRLF bytes. `MANIFEST.json` recorded that byte hash, while `.gitattributes` declares repository text as LF. Git normalized the committed blob, so every fresh GitHub checkout correctly contained LF bytes but no longer matched the pre-add manifest hash.

### Correction

- canonical evidence text is normalized to LF;
- manifest is regenerated from the committed-byte form;
- `release_manifest.generate()` refuses eligible UTF-8 text containing CR/CRLF instead of freezing an unstable hash;
- `validate()` reports `manifest_noncanonical_text_eol` when such bytes are present;
- `audit_spec.py` independently rejects non-canonical tracked UTF-8 text;
- CI validates the fresh checkout manifest immediately after checkout, before install/test.

This preserves byte-level manifest integrity rather than weakening validation by normalizing bytes during hashing.

## G2 — transaction journal mixed canonical and lexical Windows paths

`FileTransaction._relative()` performed confinement against `path.resolve()` / resolved documentation root, then serialized the journal path using the original lexical path against the original lexical root. On Windows a single physical directory can be named through a long path or an 8.3 alias such as `RUNNER~1`. The target therefore passed the canonical confinement check but `Path.relative_to()` could still fail on the lexically different spelling.

### Correction

The journal relative path is now derived from the same resolved target/root identities that passed confinement. Existing symlink/path escape checks are unchanged. A portable regression constructs two lexically different paths that resolve to one documentation root, so the invariant is tested without depending on host-specific 8.3 configuration. Existing Windows crash/recovery tests remain the end-to-end guard on GitHub-hosted Windows.

## Assurance additions

- CRLF manifest-generation refusal regression;
- canonical resolved transaction-path regression;
- repository contract test requires an early `Checkout manifest integrity` CI step before installation;
- ordinary CI continues to run Ubuntu/Python 3.11 and Windows/Python 3.14;
- release workflow performs the same pre-install checkout integrity gate.

## Acceptance requirements

- targeted regressions pass;
- full source suite and subtests pass;
- `audit_spec.py`, global axis audit, manifest validation and lifecycle pass;
- release performance gate remains within the accepted budget;
- dev20 wheel clean-install/pip-check and source parity pass;
- manifest-only Git bootstrap stays clean after tests/audits;
- final ZIP exactly matches manifest + `MANIFEST.json`;
- after push, both Ubuntu and Windows GitHub Actions jobs pass from a fresh checkout.

## Axis impact

- DAX15: transaction/crash/recovery path identity hardening;
- DAX19: assurance now reproduces both defect classes;
- DAX20: Git transport/checkout bytes and release manifest are synchronized.

No new ambiguity or blocking product question was created.

## Candidate evidence completed before GitHub push

- targeted defect regressions: PASS;
- full source suite: **232 passed, 1 expected platform skip, 253 subtests passed**;
- specification audit: PASS;
- global axis audit: zero findings;
- release manifest validation: PASS;
- bundled lifecycle: PASS;
- normalized Linux performance gate: PASS;
- dev20 clean wheel install / `pip check` / product verify: PASS;
- wheel/source parity: **20 / 20** runtime modules identical;
- literal Git normalization probe (`git add` → commit → fresh `git clone`): manifest PASS immediately after checkout; the historical Windows evidence is LF in the clone;
- fresh-clone source suite/spec/axes/manifest/lifecycle: PASS;
- fresh-clone editable install was exercised locally with `--no-build-isolation` because the build environment has no package-index network access; after the run `git status --porcelain` remained empty. GitHub Actions keeps the normal `pip install -e '.[test]'` path and is the remaining authoritative install/Windows checkout gate.

Evidence: `plan/evidence/github_checkout_portability/`.

## Remaining acceptance gate

Push the candidate to GitHub and require both matrix jobs (Ubuntu/Python 3.11 and Windows/Python 3.14) to pass from the fresh repository checkout. Until that happens this correction remains candidate, even though all local/package/Git-roundtrip gates pass.
