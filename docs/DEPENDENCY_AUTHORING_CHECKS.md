# Dependency Authoring Checks — known error patterns

Use these checks when creating/changing a dependency, formula or dependent assertion, or when investigating an unexpected update/review result. They apply the existing [DAX acceptance axes](../plan/ACCEPTANCE_AXES.md) to project authoring; they are not a second axis registry or a new runtime validator.

Do not repeat the entire catalogue manually after every ordinary source edit. Once a connection is correctly configured, the normal [sync/review loop](AI_USAGE_PROTOCOL.md#5-default-editsyncreviewverify-loop) tracks current values and reports attention. Revisit the relevant checks when the dependency's definition or intended meaning changes.

## 1. Known errors and their axes

| ID | Error pattern | What to check | Existing axes |
|---|---|---|---|
| DAE01 | The consumer relies on information absent from the declared source slice. | Identify each value/assumption used by the consumer and locate the exact canonical or derived source that supplies it. A reference to another owner is not the referenced owner's value. | DAX06, DAX08 |
| DAE02 | A dependency-derived value is maintained as a copied block or constant. | Check whether the apparently derived value actually comes from a tracked read/formula. Independent canonical constants remain legitimate. | DAX05, DAX06, DAX11 |
| DAE03 | The producer reads a real input outside tracked APIs, or treats a navigation link as a registered dependency. | Inspect dependency-bearing I/O and registration; confirm the actual edges in graph/explain. | DAX06, DAX10 |
| DAE04 | The dependency slice/comparator is broader or narrower than its intended use. | Check selected fields, Markdown bounds and comparison policy against the consumer's actual requirement. Test a relevant and an irrelevant edit where practical. | DAX06, DAX07, DAX08 |
| DAE05 | An independent field is read through a final whole-document builder. | Check whether resolving the field unnecessarily demands siblings or recurses into the consumer. Use independent providers for independently computed fields. | DAX06, DAX10 |
| DAE06 | A valid receipt or old review is treated as proof that the dependency model covers every real assumption. | Distinguish current validity of registered inputs from completeness of the source map and from a semantic judgment. | DAX06, DAX08, DAX09 |

These are authoring mistakes to look for, not claims that all projects contain them. Missing sources, real cycles, unavailable builders and stale review tokens already have runtime diagnostics. A dependency that was never declared cannot in general be inferred from a successful structural check.

## 2. DAE01 — the declared source must supply what the consumer uses

Example:

- C owns `archive_after_days = 30`.
- B's prose says "use the period defined by policy C". This source slice contains a reference to C; it does not expose the numeric period.
- A instructs an operator to archive on day 31, based on the period plus one day, but its only dependency is B's unchanged prose.

Changing C to 45 does not change that B slice. A check of the declared B content therefore cannot establish whether A's day is current. The missing source edge is the authoring error. Do not assume a transitive content relationship supplies an unexposed value.

When A uses C's period, read/depend on C's exact field directly. A deterministic producer can express the stated formula:

```python
def build(ctx):
    period = ctx.read("resource://policies/C#/archive_after_days")
    return {"archive_day": period + 1}
```

The resulting day changes from 31 to 46 through normal sync. No separate semantic review of that programmed arithmetic is required. If A instead contains independently authored prose whose validity depends on the period, register a semantic dependency on that same exact source field:

```python
def register_semantic_dependencies(registry):
    registry.register(
        "file://instructions/A.md",
        [("resource://policies/C#/archive_after_days", "exact")],
        rule_id="instructions.A-archive-period",
    )
```

Retain A's dependency on B if A also uses a procedure or assertion actually supplied by B. Add the needed source rather than deleting other useful dependencies by default.

An indirect route is also correct when B exposes the needed tracked derived field, for example `resource://contracts/B#/archive_after_days`, whose producer reads C's period. Then A can depend on that B field. The engine resolves its current value; a redundant direct A-to-C edge is not required merely because C is upstream. If B's selected public value stays unchanged after a prerequisite change, a value consumer may correctly remain valid.

The general check is **source coverage**, not "always depend on every transitive upstream resource": does the selected source carry the value/contract/context on which this consumer actually relies?

## 3. DAE02 and DAE03 — preserve dependency capture

A builder that reads B's description but returns a copied `31` does not capture the period used to choose that constant. Reading some related source is not sufficient; the actual formula inputs must be tracked. Replace maintained copies with source reads/formulas where the project contract calls for derived content.

Dependency-bearing reads use `ctx.read`, `ctx.get` or the tracked FieldPlan API. Direct filesystem/network I/O is not automatically captured. Ordinary Markdown links and HTML anchors provide navigation; they do not register a computational or semantic dependency. See [Dependency Model](DEPENDENCY_MODEL.md) and [Field Dependencies](FIELD_DEPENDENCIES.md).

## 4. DAE04 — choose a sufficient, relevant slice

Use the source field/fragment needed by the assertion. A whole-file rule may create review after unrelated edits; a truncated fragment may miss a changed definition. A Markdown anchor identifies a location, not a universal semantic extent. Native `file://` refs are whole-file only; a project producer may read tracked canonical Markdown and expose an explicitly bounded derived value through a `resource://...#/field` source.

Do not select "anchor to next heading" as a universal ownership rule. Check the actual section/contract bounds, including missing or ambiguous boundaries, and fail rather than silently selecting unrelated text. Choose a comparator that preserves distinctions used by the consumer.

Broad reads are appropriate when the output preserves the whole raw object or uses the whole contract. The helper's whole raw binding/override presence tracking and package-wide code revision can conservatively reevaluate targets; that documented behavior is not automatically evidence of an incorrect source map. Distinguish extra machine evaluation from an unnecessary semantic review of a consumer.

## 5. DAE05 — demand the required computational unit

Reading a child of one atomic producer completes that producer. If B.a1 is independent of B.g1, but a field producer requests the final `views/B`, it can unnecessarily demand B.g1 or create a false whole-document recursion. Declare independent providers and use FieldPlan reads of the needed field. A real field cycle remains an error. See [Field Dependencies](FIELD_DEPENDENCIES.md#1-document-references-and-computation-cycles-are-different).

## 6. DAE06 — interpret valid evidence within its scope

Receipts prove which declared inputs were consumed/compared; they do not discover every assumption in prose or code. A project may be structurally valid while DAE01 leaves an actual assumption outside its source map.

For semantic attention, review the current packet and use its current context token; an old reviewer decision does not settle changed current inputs. Conversely, an unchanged needed value is not a reason to demand a new semantic verdict. Engine checks expose context changes; they do not invent meaning. See [Semantic Review](SEMANTIC_REVIEW.md).

## 7. Bounded authoring verification

For the connection being created or changed:

1. Identify the consumer's used values/assumptions and their owners; apply DAE01 before choosing the source ref.
2. Choose deterministic inclusion/calculation versus semantic review, then the exact sufficient source slice.
3. Inspect registration and graph/explain evidence. For an indirect derived field, confirm its producer captures the prerequisites; do not add redundant upstream edges to every consumer.
4. Where practical, use a disposable project copy to change the relevant input and inspect the expected update/attention. Also check a nearby unused input does not create unnecessary consumer review. Account for documented conservative machine reevaluation.
5. Use the normal sync/review/verify route. Record only useful evidence for the applicable checks, not a claim that every axis was automatically proved.

Correct dependency authoring comes before proposing a new propagation mechanism. General semantic-chain behavior requires a concrete case that remains problematic after actual sources and needed contracts are correctly represented.
