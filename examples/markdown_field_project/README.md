# A tracked field from canonical Markdown

This copyable WF06 example keeps the canonical policy in ordinary Markdown,
extracts one author-selected responsibility into a derived field, composes a
nested FieldPlan value and renders an automatically updated quotation. Two
independently authored decisions demonstrate selected-section and whole-file
semantic review. Runtime: `0.1.0.dev25`.

Start with the [environment/root/trust preflight](../../docs/CLEAN_CHAT_QUICKSTART.md).
Inspect and trust `docengine_project/**` before execution. The helper `fields.py`
is copied unchanged from `nested_field_project`; formulas, bounds, rules and
renderer are project-owned. No core runtime edits or Markdown-to-JSON migration
are needed. No receipt or prior semantic approval is shipped.

## Source, fields and ownership

| Identity | Role |
|---|---|
| `docs/canonical/policy.md` | Canonical policy prose |
| `resource://source/policy#/reuse` | Derived text between two explicitly selected unique bounds |
| `resource://fields/reuse_text#/value` | Independent provider for `Guide#/sections/reuse/text` |
| `docs/_structured/inputs/guide.json` | Raw local title/note and object shape |
| `resource://views/guide` | Complete composition; descriptor owns `docs/views/guide.md` |
| `file://decisions/reuse.md` | Semantic consumer of the selected reuse-policy field |
| `file://decisions/full_policy.md` | Semantic consumer of the complete canonical file |

Code mirrors its targets under `builders/source`, `builders/fields`,
`builders/views` and `dependency_rules/decisions`; package registration activates
those modules. The derived source and internal field do not need descriptor JSON.

`builders/source/policy.py` reads through `ctx.read`, preserving dependency
capture. Its bounds are `<a id="reuse-policy"></a>` and
`<a id="review-process"></a>`. They were chosen for this policy's actual extent.
Missing, duplicate or inverted bounds fail explicitly. An anchor identifies a
location; it does not imply a universal "until next heading" semantic extent.
Native `file://canonical/policy.md#reuse-policy` addressing is unsupported.

The generated guide identifies its owner and preserves the selected HTML anchor.
This fixture's selected passage has no relative Markdown links. When projecting
a passage containing such links to another folder, adapt its renderer to preserve
their destinations; extraction alone does not rebase links or discover prose meaning.

## Copy and run

Run from the engine checkout to print a new `<root>` outside it:

```bash
python -c "import shutil, tempfile; from pathlib import Path; p = Path(tempfile.mkdtemp(prefix='gdm-')) / 'project'; shutil.copytree('examples/markdown_field_project', p); print(p)"
```

Install the bundled wheel following Quickstart. Replace `<root>` with the printed
path in every command. A fresh sync updates the quotation and returns **exit 2**
because the two semantic decisions still require an explicit review:

```bash
docengine sync --project-root <root> --json
docengine graph --project-root <root> --json
docengine explain file://decisions/reuse.md --project-root <root> --json
```

Inspect the current packet and decide whether the decision is valid against the
selected policy. Use that packet's `review_context_id` for initial validation:

```bash
docengine validate file://decisions/reuse.md --result still-valid --reason "Reviewed the current local reuse decision against the selected canonical policy" --review-context reviewctx-... --actor-kind human --project-root <root> --json
docengine explain file://decisions/full_policy.md --project-root <root> --json
docengine validate file://decisions/full_policy.md --result still-valid --reason "Reviewed the complete policy context for this decision" --review-context reviewctx-... --actor-kind human --project-root <root> --json
docengine sync --project-root <root> --json
docengine verify --project-root <root> --json
```

Use the separate current token from each target's packet. The example reason
texts are illustrative; record your actual review reason. A later edited target
uses `updated` after review. Do not run blanket validation to clear attention.

## Edit and inspect

| Change in the copied project | Expected result |
|---|---|
| Edit Supporting context outside the bounds | Source producer reevaluates; selected quotation stays byte-identical; only the whole-file decision requires review |
| Edit the selected reuse-policy passage | Sync updates the quotation; both semantic consumers require review |
| Change an input after obtaining a packet | Old review token is rejected; obtain and review a fresh packet |
| Edit a previously reviewed decision | `still-valid` is rejected; fresh reviewed `updated` is required |
| Remove/duplicate either bound or invert their order | Sync fails and retains the previous complete generated guide |
| Hand-edit the generated guide | Verify reports drift; sync restores the projection |

After a dependency is correctly configured, use the ordinary sync/review/verify
loop. Recheck bounds/source coverage when changing the connection itself; do not
repeat the whole authoring checklist after every normal source edit. See
[Field Dependencies](../../docs/FIELD_DEPENDENCIES.md),
[Semantic Review](../../docs/SEMANTIC_REVIEW.md) and
[known authoring errors](../../docs/DEPENDENCY_AUTHORING_CHECKS.md).

## Repeat the executable checks

With the installed wheel, run from the engine checkout:

```bash
python examples/markdown_field_project/check_example.py
```

This creates a short temporary copy, executes the cases above using CLI commands,
and prints a JSON result. **CI decisions are synthetic and confined to the demo**;
the script does not approve your real documents. It needs no pytest, GUI, UAC or
symlink privilege. To retain the project and per-command report for investigation:

```bash
python examples/markdown_field_project/check_example.py --work-dir <new-empty-path> --report <report-path>
```

The destination must not exist. Before an unexpected assertion the disposable
project retains `example-check-report.json` with exact CLI outcomes. The normal
repository suite also runs this route in `tests/test_markdown_field_project.py`.
