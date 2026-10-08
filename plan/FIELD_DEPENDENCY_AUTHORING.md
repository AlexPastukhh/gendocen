# Project-owned field dependency authoring

**Historical implementation:** `FIELD-AUTHORING-1`, flat helper. **Implemented follow-up:** [`FIELD_DEPENDENCY_EXPANSION.md`](FIELD_DEPENDENCY_EXPANSION.md), `FIELD-EXPANSION-1` (runtime `0.1.0.dev23`). That follow-up expands nested fields, fixes transitive-source failure handling and introduces operation-scoped reuse. The implementation/evidence below preserve the historical flat baseline; current implementation and acceptance are recorded in the follow-up.

## Decision and scope

The user selected the project-layer proposal and requested complete documentation for a new chat in the existing onboarding/workflow style. Implement a copyable helper and runnable example using the accepted public runtime. Formulas and source ownership remain project-authored; no native field-target API, new ref scheme, persisted schema or runtime-wheel change is introduced.

Canonical decision for this additive authoring work: `FIELD-AUTHORING-1`. Runtime stays `0.1.0.dev22`; existing P0–P8 acceptance records and historical evidence are preserved. The manifest is regenerated through the release tool for the changed documentation/example/test inventory. The Python package source, packaging metadata, README long description and bundled wheel are unchanged, so a runtime version bump/rebuilt wheel is not required.

## Implemented route

- `examples/field_dependency_project/docengine_project/fields.py` provides explicit required inputs, computed providers, optional raw precedence, tracked reads, registration and complete view composition.
- Each computed field has a distinct internal whole-resource target holding `{"value": ...}`. Final view builders gather those values instead of being computation prerequisites.
- Required missing inputs never invoke guessed derived builders. Undeclared fields, duplicate providers, shared computed targets and undeclared raw/computed ownership conflicts are errors.
- Presence tracking uses a whole raw-object dependency; consumer reads use exact internal value slices. Existing engine session caching, source revisions and receipts remain authoritative.
- Mirrored producer/view modules are explicitly registered. Internal resources have no descriptor JSON; final materialized views have descriptors.
- New-chat routing is Quickstart → WF06 → `FIELD_DEPENDENCIES.md` → executable fixture; Code Model, Build Runtime and AI Usage Protocol point to the same route.

## Acceptance scenarios

The regression suite `tests/test_field_dependency_project.py` exercises:

1. On-demand acyclic cross-document computations without unrelated field evaluation; shared prerequisites run once within one build session.
2. Missing required inputs and undeclared fields produce source/provider diagnostics rather than inferred computation cycles.
3. Actual circular producers are rejected with their internal-resource cycle path.
4. Explicit raw override presence, including null, and JSON Pointer escaping for literal field-name characters.
5. Unauthorised raw/computed conflicts, duplicate providers, target ownership and sealed declarations.
6. Fresh CLI sync/graph/verify, exact materialized values, prerequisite mutation, ignored unused input and override addition/removal.
7. Failed rebuild of a missing required input returns a domain error and preserves previously materialized Markdown.
8. Zero-context doc routing and explicit project-root commands.

Ordinary repository gates remain the checks in `docs/REPOSITORY_WORKFLOW.md`. This decision record describes reproducible scenarios; it does not replace their execution results or claim another platform has been tested.

## Carried boundaries and return triggers

- **Accepted scope:** logical output fields are top-level. Required source refs can address nested values; overrides address one top-level raw field. Overlapping nested output producers/atomic groups require a separate contract if a real project needs them.
- **Deferred native API:** if direct field-target registration, unified field diagnostics or common scheduling becomes necessary, revisit runtime integration with receipts/invalidation/transactions. The demonstrated resource-based approach does not require that work.
- **Accepted cache boundary:** separate sessions can recompute shared producers. Measure before adding broader caching; current raw/code evidence must govern reuse. Return when producers or projects make repeat execution materially expensive.
- **Cooperative trust:** helper/producers remain project Python under the existing tracked-read contract. No sandbox guarantee is added.

These are explicit limitations/defaults, not unresolved blockers for the selected project helper.

The user subsequently promoted nested output composition and operation-scoped reuse into the next implementation scope. Those two boundaries above describe the original flat implementation only; the implemented follow-up supersedes them. Recursive depth remains accepted; no limit increase or iterative executor is planned. See `FIELD-EXPANSION-1` for the current decisions, contracts, acceptance criteria and release obligations.

## Validation — 2026-10-07

On Linux/Python 3.12, the complete test suite passed: **284 passed, 1 skipped**, including 8 new field-helper/fixture tests. The existing platform-specific skip remains visible; Windows execution is left to the repository CI matrix. Required ordinary-commit gates passed: `audit_spec.py`, `audit_axes.py --json`, `release_manifest.py validate --json`, and `release_check.py --json`. New guide/fixture local links and explicit-root commands were checked. Runtime/package source and bundled wheel bytes were not changed.

The initial local Git tree was verified equal to the supplied/current main tree `ee1ca1b233b66cc803760e1576077ab0621f3b16` at commit `df63405953f9de87ef0668e1d6bd99046694bd5c`. At the user's request, changes remain in the local working copy; creating a remote branch/PR is deferred. No main-branch update or release/tag is part of this work.
