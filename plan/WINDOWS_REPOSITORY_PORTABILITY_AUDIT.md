# Windows Repository Portability Audit — v0.27

Date: 2026-10-03
Status: **PASS — real Windows/Python 3.14 gate completed; final package freeze**
Runtime distribution: **0.1.0.dev19**
Specification/runtime package: **0.27.0-p8-windows-repo-ready-final**

## Trigger

A real Windows 11 / Python 3.14 checkout of v0.26 ran the documented repository checks and reported five failing tests. Independent classification found three root causes rather than five independent defects.

## Confirmed defects and corrections

### W1 — self-audit depended on the host ANSI code page

`tools/audit_spec.py` used `Path.read_text()` without an explicit encoding for canonical UTF-8 JSON. On the observed Windows host this selected cp1251 and raised `UnicodeDecodeError`.

**Correction:** all canonical reads in `audit_spec.py` are explicit UTF-8; test fixture reads were made explicit UTF-8 as well.

### W2 — synthetic benchmark imported Unix-only `resource` unconditionally

`tools/benchmark_p7.py` failed to import on Windows, which also broke the P8 clean-source benchmark reproducibility test.

**Correction:** POSIX keeps `resource.getrusage`; Windows obtains PeakWorkingSetSize in KiB with standard-library `ctypes`/Process Status API. macOS `ru_maxrss` bytes are normalized to KiB. No new dependency is added.

### W3 — locking regression contradicted the accepted Windows support contract

The runtime intentionally serializes Windows readers because stdlib `msvcrt` has no shared-lock primitive, but the old test required POSIX shared-reader behavior on every platform.

**Correction:** POSIX retains the shared-reader test. Windows has a separate regression that requires the second reader to fail safely with normal `runtime_busy`, matching A7/P8-Q8.E3. Runtime semantics are unchanged.

### W4 — repository CI had Linux-only evidence

The v0.26 Git persistence audit passed only on Linux, so it could not detect W1–W3.

**Correction:** ordinary CI now includes Ubuntu/Python 3.11 and Windows/Python 3.14. The release workflow retains the canonical normalized performance gate on Ubuntu and adds a Windows portability job running tests/spec/axes/manifest/lifecycle. Git-clean checks use a portable Python command rather than POSIX `test -z`.

## User-observed unaffected checks

On the failing v0.26 Windows checkout, `audit_axes.py`, `release_manifest.py validate`, and the full bundled `release_check.py` lifecycle already passed. The corrections therefore target repository/tooling portability rather than core dependency/materialization/semantic behavior.

## Acceptance requirements

- Linux full source suite;
- UTF-8 spec audit;
- global axis audit and manifest validation;
- release lifecycle;
- normalized performance gate;
- dev19 wheel/source parity and clean install;
- manifest-only Git bootstrap;
- exact ZIP member/CRC gate;
- Windows CI contract explicitly present for Python 3.14.

A Windows GitHub Actions run is the authoritative ongoing cross-platform regression guard after push.

## Candidate evidence completed in the build environment

- full source suite: **230 passed, 253 subtests passed, 1 expected platform skip**;
- `tools/audit_spec.py`: PASS;
- global axis audit: zero findings;
- release manifest validation: PASS;
- bundled lifecycle: PASS;
- normalized performance gate on Linux: PASS (`plan/evidence/windows_portability/performance_gate_linux.json`);
- dev19 clean wheel install and `pip check`: PASS;
- wheel/source parity: **20 / 20** runtime modules identical;
- literal manifest-only Git probe: tests/spec/axes/manifest/lifecycle PASS and `git status --porcelain` empty.

## Real Windows acceptance completed

The corrected v0.27 tree was rerun on the same real Windows 11 / Python 3.14 checkout class that exposed W1–W3. The targeted portability suite passed **10 tests with 1 expected platform skip**. The full source suite then passed **230 tests with 1 expected platform skip**; `audit_spec.py`, `audit_axes.py`, manifest validation and the bundled release lifecycle all passed. The normalized release benchmark also passed on Windows with **57,296 KiB peak RSS** and **0.2751 normalized total ratio** against the blocking limits.

Raw user-host evidence is retained at `plan/evidence/windows_portability/windows_real_host_gate_full.txt`. This closes the v0.27 Windows acceptance gate; ongoing regression protection remains the `windows-latest` CI job.
