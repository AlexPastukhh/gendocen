#!/usr/bin/env python3
"""Derive global release-axis closure from canonical phase execution records.

P8 post-axis semantics:
- accepted phases normally require pass/not_applicable criteria and axes;
- a historical partial is legal only when a canonical carried_release_gate names the
  exact source criterion/axis and a concrete later phase criterion;
- final release requires every carried gate to be resolved by an accepted target
  phase whose target criterion and target axis pass;
- path-like evidence references must resolve inside the release tree.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

DEFAULT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH_PREFIXES = (
    "README.md", "START_HERE_AGENT.md", "OPEN_QUESTIONS_AND_AMBIGUITIES.md",
    "MANIFEST.json", "pyproject.toml", "docs/", "plan/", "spec/", "src/",
    "tools/", "tests/", "examples/", "dist/",
)


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_path(ref: str) -> str | None:
    """Return the repo-relative path portion for path-like evidence refs.

    Question provenance tokens such as ``implementation-plan-default`` and
    ``conversation-design-decision`` are intentionally not filesystem refs.
    Pytest node ids resolve through their file path prefix.
    """
    base = ref.split("::", 1)[0].rstrip("/")
    if any(base == prefix or base.startswith(prefix) for prefix in PATH_PREFIXES):
        return base
    return None


def iter_evidence_refs(rec: dict[str, Any]):
    phase = rec.get("phase_id", "?")
    for criterion in rec.get("acceptance_criteria", []):
        for ref in criterion.get("evidence_refs", []):
            yield phase, f"criterion:{criterion.get('id')}", ref
    for axis in rec.get("axis_reviews", []):
        for ref in axis.get("evidence_refs", []):
            yield phase, f"axis:{axis.get('axis_id')}", ref
    for key in ("pre_execution_questions", "emergent_questions"):
        for question in rec.get(key, []):
            for ref in question.get("evidence_refs", []):
                yield phase, f"question:{question.get('id')}", ref
    for index, entry in enumerate(rec.get("implementation_log", [])):
        for ref in entry.get("evidence_refs", []):
            yield phase, f"implementation_log:{index}", ref
    for gate in rec.get("carried_release_gates", []):
        for ref in gate.get("evidence_refs", []):
            yield phase, f"carried_release_gate:{gate.get('id')}", ref


def audit(root: pathlib.Path, *, check_evidence_refs: bool = True) -> dict[str, Any]:
    axes = load_json(root / "spec/registries/ACCEPTANCE_AXES.json")["axes"]
    record_pairs = []
    for path in sorted(
        (root / "plan/phase_records").glob("P*_EXECUTION_RECORD.json"),
        key=lambda p: int(p.name.split("_")[0][1:]),
    ):
        record_pairs.append((path, load_json(path)))
    records = {rec["phase_id"]: rec for _, rec in record_pairs}
    findings: list[dict[str, Any]] = []
    carry_summaries: list[dict[str, Any]] = []

    # Referential integrity of canonical evidence paths.
    if check_evidence_refs:
        for _, rec in record_pairs:
            for phase, owner, ref in iter_evidence_refs(rec):
                rel = evidence_path(ref)
                if rel is not None and not (root / rel).exists():
                    findings.append({
                        "code": "evidence_ref_missing",
                        "phase": phase,
                        "owner": owner,
                        "ref": ref,
                    })

    for _, rec in record_pairs:
        phase = rec["phase_id"]
        if phase != "P8" and rec["status"] != "accepted":
            findings.append({"code": "prior_phase_not_accepted", "phase": phase, "status": rec["status"]})

        gates = rec.get("carried_release_gates", [])
        by_criterion = {g["source_criterion_id"]: g for g in gates}
        by_axis = {g["axis_id"]: g for g in gates}

        if rec["status"] == "accepted":
            for criterion in rec.get("acceptance_criteria", []):
                status = criterion.get("status")
                if status in {"pass", "not_applicable"}:
                    continue
                gate = by_criterion.get(criterion.get("id"))
                if status == "partial" and gate and gate.get("axis_id") in criterion.get("axis_ids", []):
                    continue
                findings.append({
                    "code": "accepted_phase_incomplete_criterion",
                    "phase": phase,
                    "criterion": criterion.get("id"),
                    "status": status,
                })

            for axis in rec.get("axis_reviews", []):
                status = axis.get("status")
                if status in {"pass", "not_applicable"}:
                    continue
                gate = by_axis.get(axis.get("axis_id"))
                if status == "partial" and gate:
                    continue
                findings.append({
                    "code": "accepted_phase_incomplete_axis",
                    "phase": phase,
                    "axis": axis.get("axis_id"),
                    "status": status,
                })

            unresolved = [
                q["id"]
                for key in ("pre_execution_questions", "emergent_questions")
                for q in rec.get(key, [])
                if q.get("blocking") and q.get("status") != "answered"
            ]
            if unresolved:
                findings.append({
                    "code": "accepted_phase_unresolved_blocking_questions",
                    "phase": phase,
                    "questions": unresolved,
                })

        criteria_by_id = {c["id"]: c for c in rec.get("acceptance_criteria", [])}
        for gate in gates:
            gate_id = gate.get("id")
            source_criterion = criteria_by_id.get(gate.get("source_criterion_id"))
            target = records.get(gate.get("target_phase_id"))
            summary = {
                "id": gate_id,
                "source_phase": phase,
                "source_criterion": gate.get("source_criterion_id"),
                "axis": gate.get("axis_id"),
                "target_phase": gate.get("target_phase_id"),
                "target_criterion": gate.get("target_criterion_id"),
                "status": gate.get("status"),
            }
            carry_summaries.append(summary)
            if source_criterion is None:
                findings.append({"code": "carried_gate_source_criterion_missing", **summary})
                continue
            if source_criterion.get("status") != "partial" or gate.get("axis_id") not in source_criterion.get("axis_ids", []):
                findings.append({"code": "carried_gate_source_mismatch", **summary})
            if target is None:
                findings.append({"code": "carried_gate_target_phase_missing", **summary})
                continue
            target_criterion = next((c for c in target.get("acceptance_criteria", []) if c.get("id") == gate.get("target_criterion_id")), None)
            if target_criterion is None:
                findings.append({"code": "carried_gate_target_criterion_missing", **summary})
                continue
            if gate.get("axis_id") not in target_criterion.get("axis_ids", []):
                findings.append({"code": "carried_gate_target_axis_mismatch", **summary})
            if gate.get("status") == "resolved":
                if target.get("status") != "accepted" or target_criterion.get("status") != "pass":
                    findings.append({"code": "carried_gate_claimed_resolved_without_target_pass", **summary})
                target_axis = next((a for a in target.get("axis_reviews", []) if a.get("axis_id") == gate.get("axis_id")), None)
                if target_axis is None or target_axis.get("status") != "pass":
                    findings.append({"code": "carried_gate_claimed_resolved_without_axis_pass", **summary})

    p8 = records.get("P8")
    p8_axes: dict[str, dict[str, Any]] = {}
    if p8 is None:
        findings.append({"code": "p8_record_missing"})
    else:
        if p8.get("status") != "accepted":
            findings.append({"code": "p8_not_accepted", "status": p8.get("status")})
        p8_axes = {a["axis_id"]: a for a in p8.get("axis_reviews", [])}
        promoted = {g["axis_id"] for rec in records.values() for g in rec.get("carried_release_gates", [])}
        required = set(a["id"] for a in axes if a.get("release_gate")) | promoted
        missing = sorted(required - set(p8_axes))
        if missing:
            findings.append({"code": "p8_release_axes_missing", "axes": missing})
        for axis in sorted(required):
            item = p8_axes.get(axis)
            if item is None:
                continue
            if item.get("status") != "pass":
                findings.append({"code": "release_axis_not_pass", "axis": axis, "status": item.get("status")})
            if not item.get("evidence_refs"):
                findings.append({"code": "release_axis_missing_evidence", "axis": axis})
        pending = [c["id"] for c in p8.get("acceptance_criteria", []) if c.get("status") != "pass"]
        if pending:
            findings.append({"code": "p8_acceptance_criteria_not_pass", "criteria": pending})
        unresolved = [
            q["id"]
            for key in ("pre_execution_questions", "emergent_questions")
            for q in p8.get(key, [])
            if q.get("blocking") and q.get("status") != "answered"
        ]
        if unresolved:
            findings.append({"code": "p8_unresolved_blocking_questions", "questions": unresolved})
        open_carries = [g for g in carry_summaries if g.get("status") != "resolved"]
        if open_carries:
            findings.append({"code": "final_release_has_open_carried_gates", "gates": open_carries})

    release_axes = sorted(a["id"] for a in axes if a.get("release_gate"))
    promoted_axes = sorted({g["axis"] for g in carry_summaries})
    return {
        "ok": not findings,
        "phase_count": len(record_pairs),
        "release_gate_axes": release_axes,
        "promoted_release_axes": promoted_axes,
        "carried_release_gates": carry_summaries,
        "findings": findings,
        "p8_axis_statuses": {k: v.get("status") for k, v in sorted(p8_axes.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    print(json.dumps(result, sort_keys=True) if args.json else json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
