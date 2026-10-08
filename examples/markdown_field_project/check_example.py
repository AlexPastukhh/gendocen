"""Exercise a fresh disposable copy with installed docengine; no pytest required."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import shutil
import tempfile

from docengine.cli import main as engine_main

FIXTURE = Path(__file__).resolve().parent
NARROW = "file://decisions/reuse.md"
WHOLE = "file://decisions/full_policy.md"
START = '<a id="reuse-policy"></a>'
END = '<a id="review-process"></a>'


def run_checks(project):
    """Use a new destination; synthetic decisions apply only to this demo copy."""
    shutil.copytree(FIXTURE, project, ignore=shutil.ignore_patterns("__pycache__"))
    report = {"scope": "Disposable demo; synthetic CI decisions, not real-policy approval.",
              "project": str(project), "commands": [], "scenarios": []}

    def command(name, *args, expected=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = engine_main([name, *args, "--project-root", str(project), "--json"])
        result = json.loads(out.getvalue())
        entry = {"command": name, "args": list(args), "exit": code,
                 "meta": result["meta"], "errors": result["errors"]}
        report["commands"].append(entry)
        # Retain exact command outcome before an assertion, including failures.
        (project / "example-check-report.json").write_text(
            json.dumps(report, indent=2)+"\n", encoding="utf-8")
        if expected is not None:
            assert code == expected, entry
        return result

    def packet(target):
        result = command("explain", target)
        assert result["meta"]["exit_code"] in (0, 2), result["errors"]
        return result["data"]

    def validate(target, result="still-valid", token=None, expected=0):
        token = token or packet(target)["review_context_id"]
        return command("validate", target, "--result", result, "--reason",
                       "Synthetic demo lifecycle check; no real-policy approval.",
                       "--actor-kind", "ci", "--review-context", token, expected=expected)

    def statuses():
        result = command("check")
        assert result["meta"]["exit_code"] in (0, 2), result["errors"]
        return {r["target"]: r["status"] for r in result["data"]["results"]}

    def scenario(name):
        report["scenarios"].append({"name": name, "ok": True})

    def write(path, text):
        path.write_text(text, encoding="utf-8", newline="\n")

    source = project / "docs/canonical/policy.md"
    view = project / "docs/views/guide.md"
    command("sync", expected=2)
    assert view.is_file() and START in view.read_text(encoding="utf-8")
    rows = statuses()
    assert rows[NARROW] == rows[WHOLE] == "review_required", rows
    for target in (NARROW, WHOLE):
        validate(target)
    command("sync", expected=0)
    command("verify", expected=0)
    graph = command("graph", expected=0)
    assert "resource://source/policy#/reuse" in json.dumps(graph)
    assert "file://canonical/policy.md" in json.dumps(graph)
    scenario("fresh baseline, tracked graph, nested composition and preserved anchor")

    original = source.read_text(encoding="utf-8")
    good = view.read_bytes()
    write(source, original + "\nAdjacent supporting-context edit.\n")
    rows = statuses()
    assert rows[NARROW] == rows["resource://views/guide"] == "valid", rows
    assert rows[WHOLE] == "review_required", rows
    command("sync", expected=2)
    assert view.read_bytes() == good
    validate(WHOLE)
    command("sync", expected=0)
    scenario("adjacent edit preserves selected quotation and only whole-file review changes")

    text = source.read_text(encoding="utf-8")
    write(source, text.replace(END, "Selected policy annotation v2.\n\n" + END, 1))
    rows = statuses()
    assert rows[NARROW] == rows[WHOLE] == "review_required", rows
    assert rows["resource://views/guide"] == "build_required", rows
    command("sync", expected=2)
    assert b"Selected policy annotation v2." in view.read_bytes()
    scenario("selected edit updates quotation without inventing semantic verdict")

    stale = packet(NARROW)["review_context_id"]
    write(source, source.read_text(encoding="utf-8").replace("annotation v2.", "annotation v3.", 1))
    failed = validate(NARROW, token=stale, expected=3)
    assert any("stale" in e["message"] for e in failed["errors"]), failed["errors"]
    scenario("stale packet rejected after a second source edit")

    decision = project / "docs/decisions/reuse.md"
    write(decision, decision.read_text(encoding="utf-8") + "\nLocal application inspected and updated.\n")
    failed = validate(NARROW, expected=3)
    assert any("updated" in e["message"] for e in failed["errors"]), failed["errors"]
    validate(NARROW, result="updated")
    validate(WHOLE)
    command("sync", expected=0)
    command("verify", expected=0)
    scenario("edited target needs fresh updated decision")

    valid_source = source.read_text(encoding="utf-8")
    good = view.read_bytes()
    bad_sources = {
        "missing start": valid_source.replace(START, "", 1),
        "missing end": valid_source.replace(END, "", 1),
        "duplicate start": valid_source.replace(START, START+"\n"+START, 1),
        "duplicate end": valid_source.replace(END, END+"\n"+END, 1),
        "inverted bounds": valid_source.replace(START, "TEMP_BOUND", 1).replace(END, START, 1).replace("TEMP_BOUND", END, 1),
    }
    for name, bad in bad_sources.items():
        write(source, bad)
        failed = command("sync", expected=3)
        assert failed["errors"]
        assert view.read_bytes() == good
        write(source, valid_source)
        command("sync", expected=0)
        scenario(name+" fails while retaining previous complete output")

    write(view, view.read_text(encoding="utf-8")+"\nManual generated-view drift.\n")
    command("verify", expected=3)
    command("sync", expected=0)
    assert view.read_bytes() == good
    command("verify", expected=0)
    scenario("generated drift detected and restored")
    report["ok"] = True
    (project / "example-check-report.json").write_text(
        json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, help="new destination to retain the disposable project and report")
    parser.add_argument("--report", type=Path, help="also save the successful JSON report here")
    args = parser.parse_args()
    if args.work_dir:
        report = run_checks(args.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="gdm-") as temp:
            report = run_checks(Path(temp) / "project")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
