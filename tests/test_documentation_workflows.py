import contextlib
import io
import json
import os
import re
import shutil
import shlex
import tempfile
import unittest
from pathlib import Path

from docengine.cli import main
from docengine.extensions import load_project_extension
from docengine.project import discover_roots
from docengine.resources import ResourceCatalog

ROOT = Path(__file__).resolve().parents[1]


def run_json(argv):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(argv)
    return code, json.loads(stream.getvalue())


ZERO_CONTEXT_PROJECT_COMMANDS = {
    "init", "resources", "status", "check", "diff", "explain", "graph",
    "validate", "rebuild", "materialize", "sync", "verify", "history",
    "recover", "migrate",
}


def _command_segment_end(text, start):
    """Return the end of one shell-like command occurrence in Markdown text.

    Separators are recognized outside single/double quotes. Backslash-newline is
    treated as a continuation so an explicit root on the next line belongs to
    the same command.
    """
    quote = None
    escaped = False
    i = start
    while i < len(text):
        ch = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\":
            if i + 1 < len(text) and text[i + 1] == "\n":
                i += 2
                continue
            escaped = True
            i += 1
            continue
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == "\n" or ch in ";|&":
            return i
        i += 1
    return len(text)


def _rootless_zero_context_project_commands(text):
    """Return every full-form project command whose own segment lacks a root.

    This intentionally scans all prose/code rather than only fenced or backtick
    forms. Zero-context docs use bare command names for conceptual mentions; any
    full `docengine <project-command>` spelling is therefore treated as
    executable guidance and must carry its own `--project-root`.
    """
    rootless = []
    pattern = re.compile(r"\bdocengine\s+([a-z][a-z0-9_-]*)\b")
    for match in pattern.finditer(text):
        command = match.group(1)
        if command not in ZERO_CONTEXT_PROJECT_COMMANDS:
            continue
        end = _command_segment_end(text, match.start())
        segment = text[match.start():end].strip().strip("`")
        try:
            lexer = shlex.shlex(segment, posix=False)
            lexer.whitespace_split = True
            lexer.commenters = "#"
            tokens = list(lexer)
        except ValueError:
            # Malformed shell-like text is not accepted as evidence of a root option.
            tokens = []

        def nonempty_value(token):
            token = token.strip()
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
                token = token[1:-1]
            return bool(token.strip()) and not token.lstrip().startswith("-")

        has_root_option = False
        for index, token in enumerate(tokens):
            if token == "--project-root":
                if index + 1 < len(tokens) and nonempty_value(tokens[index + 1]):
                    has_root_option = True
                    break
            elif token.startswith("--project-root="):
                value = token.split("=", 1)[1]
                if nonempty_value(value):
                    has_root_option = True
                    break
        if not has_root_option:
            rootless.append(segment)
    return rootless



class DocumentationWorkflowIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "spec/registries/USE_CASE_REGISTRY.json").read_text(encoding="utf-8"))
        self.cli = json.loads((ROOT / "spec/registries/CLI_COMMANDS.json").read_text(encoding="utf-8"))
        self.workflows = (ROOT / "docs/CORE_WORKFLOWS.md").read_text(encoding="utf-8")

    def test_every_workflow_doc_reference_exists(self):
        known = {item["id"] for item in self.registry["use_cases"]}
        referenced = set(re.findall(r"\bDOC\d{2}\b", self.workflows))
        self.assertTrue(referenced)
        self.assertEqual(referenced - known, set())

    def test_every_public_cli_command_has_v01_use_case(self):
        covered = set()
        for item in self.registry["use_cases"]:
            if item["implementation_target"] == "v0.1":
                covered.update(item["cli_commands"])
        self.assertEqual(set(self.cli["commands"]) - covered, set())

    def test_future_promote_demote_are_not_current_cli(self):
        by_id = {item["id"]: item for item in self.registry["use_cases"]}
        for doc_id in ("DOC18", "DOC19"):
            self.assertEqual(by_id[doc_id]["implementation_target"], "future")
            self.assertEqual(by_id[doc_id]["cli_commands"], [])
        current, future = self.workflows.split("# Future authoring helpers", 1)
        self.assertNotRegex(current, r"\bdocengine\s+(?:promote|demote)\b")
        self.assertIn("DOC18", future)
        self.assertIn("DOC19", future)
        self.assertIn("implementation_target=future", future)

    def test_readme_routes_new_users_to_workflows_and_examples(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/CORE_WORKFLOWS.md", text)
        self.assertIn("examples/product_tax_project/README.md", text)
        self.assertIn("examples/sample_project/README.md", text)
        self.assertLess(text.index("docs/CORE_WORKFLOWS.md"), text.index("START_HERE_AGENT.md"))

    def test_repository_workflow_matches_product_first_onboarding(self):
        text = (ROOT / "docs/REPOSITORY_WORKFLOW.md").read_text(encoding="utf-8")
        self.assertIn("README.md` → `docs/CLEAN_CHAT_QUICKSTART.md` → the relevant `docs/CORE_WORKFLOWS.md", text)
        self.assertIn("maintainer/release handoff", text)
        self.assertNotIn("START_HERE_AGENT.md` is the first file for a new AI/chat session", text)

    def test_product_fixture_uses_mirrored_builder_and_registration(self):
        project = ROOT / "examples/product_tax_project"
        mirrored = project / "docengine_project/builders/catalog/price_with_tax.py"
        self.assertTrue(mirrored.is_file())
        roots = discover_roots(project_root=project)
        catalog = ResourceCatalog.scan(roots)
        extension = load_project_extension(roots, catalog)
        self.assertTrue(extension.registry.has_target("resource://catalog/price_with_tax"))

    def test_sample_fixture_uses_mirrored_builder_and_semantic_rule(self):
        project = ROOT / "examples/sample_project"
        self.assertTrue((project / "docengine_project/builders/architecture/system_summary.py").is_file())
        self.assertTrue((project / "docengine_project/dependency_rules/architecture/rationale.py").is_file())
        roots = discover_roots(project_root=project)
        catalog = ResourceCatalog.scan(roots)
        extension = load_project_extension(roots, catalog)
        self.assertTrue(extension.registry.has_target("resource://architecture/system_summary"))
        targets = {str(rule.target) for rule in extension.semantic_registry.rules}
        self.assertIn("file://architecture/rationale.md", targets)

    def test_sample_mirrored_semantic_rule_is_authoritative(self):
        source = ROOT / "examples/sample_project"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(source, project)
            rule_path = project / "docengine_project/dependency_rules/architecture/rationale.py"
            text = rule_path.read_text(encoding="utf-8")
            text = text.replace(
                '[("resource://policies/method_policy#/allowed_methods", "set")]',
                '[("resource://architecture/overview#/title", "exact")]',
            )
            rule_path.write_text(text, encoding="utf-8")
            roots = discover_roots(project_root=project)
            catalog = ResourceCatalog.scan(roots)
            extension = load_project_extension(roots, catalog)
            rule = extension.semantic_registry.get("file://architecture/rationale.md")
            deps = [(str(dep.source), dep.comparator) for dep in rule.dependencies]
            self.assertEqual(deps, [("resource://architecture/overview#/title", "exact")])

    def test_mirrored_builder_file_without_registration_is_not_active(self):
        source = ROOT / "examples/product_tax_project"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(source, project)
            descriptor = project / "docs/_structured/catalog/unregistered.json"
            descriptor.write_text(json.dumps({
                "$docengine": {
                    "resource_id": "catalog.unregistered",
                    "resource_kind": "derived_descriptor",
                    "materialize": [{
                        "renderer": "markdown",
                        "path": "catalog/unregistered.md",
                        "path_base": "documentation_root",
                    }],
                },
                "data": {},
            }, indent=2) + "\n", encoding="utf-8")
            mirrored = project / "docengine_project/builders/catalog/unregistered.py"
            mirrored.write_text(
                "def build(ctx):\n    return {'value': 1}\n\ndef register(registry):\n"
                "    registry.register('resource://catalog/unregistered', build)\n",
                encoding="utf-8",
            )

            # Inventory sees the descriptor, but that is deliberately not proof of registration.
            code, resources = run_json(["resources", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0, resources)
            row = next(x for x in resources["data"]["resources"] if x["ref"] == "resource://catalog/unregistered")
            self.assertEqual(row["kind"], "derived")

            # An operation that actually loads/uses builders must reject the missing registration.
            code, synced = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3, synced)
            self.assertFalse(synced["ok"])
            self.assertTrue(any("registered builder" in e.get("message", "") for e in synced["errors"]))

    def test_product_tutorial_selective_invalidation_and_sync_is_executable(self):
        source = ROOT / "examples/product_tax_project"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(source, project)
            product_json = project / "docs/_structured/catalog/product.json"
            data = json.loads(product_json.read_text(encoding="utf-8"))
            data["data"]["price"] = 125
            product_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            code, checked = run_json(["check", "--project-root", str(project), "--json"])
            self.assertIn(code, (0, 2))
            row = next(x for x in checked["data"]["results"] if x["target"] == "resource://catalog/price_with_tax")
            self.assertEqual(row["status"], "build_required")
            self.assertIn("**Price:** 100", (project / "docs/catalog/price_with_tax.md").read_text(encoding="utf-8"))

            code, synced = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0, synced)
            self.assertEqual(synced["meta"]["status"], "ok")
            generated = (project / "docs/catalog/price_with_tax.md").read_text(encoding="utf-8")
            self.assertIn("**Price:** 125", generated)
            self.assertIn("**Total:** 150.0", generated)

            data = json.loads(product_json.read_text(encoding="utf-8"))
            data["data"]["unused_note"] = "changed but not consumed"
            product_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            code, checked2 = run_json(["check", "--project-root", str(project), "--json"])
            self.assertIn(code, (0, 2))
            row2 = next(x for x in checked2["data"]["results"] if x["target"] == "resource://catalog/price_with_tax")
            self.assertEqual(row2["status"], "valid")

    def test_plain_resource_requires_graph_to_detect_semantic_ownership(self):
        project = ROOT / "examples/sample_project"
        code, resources = run_json(["resources", "--project-root", str(project), "--json"])
        self.assertEqual(code, 0, resources)
        row = next(x for x in resources["data"]["resources"] if x["ref"] == "file://architecture/rationale.md")
        self.assertEqual(row["kind"], "plain")
        code, graph = run_json(["graph", "file://architecture/rationale.md", "--project-root", str(project), "--json"])
        self.assertEqual(code, 0, graph)
        self.assertEqual(graph["data"]["runtime_diagnostics"], [])
        self.assertTrue(graph["data"]["rules"])
        self.assertEqual(graph["data"]["rules"][0]["dependency_type"], "semantic_review")

    def test_sample_semantic_tutorial_establishes_baseline_before_change(self):
        source = ROOT / "examples/sample_project"
        target = "file://architecture/rationale.md"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(source, project)

            code, first = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 2, first)
            code, packet = run_json(["explain", target, "--project-root", str(project), "--json"])
            self.assertEqual(code, 2, packet)
            self.assertIn("initial_validation_required", packet["data"]["reason_codes"])
            context = packet["data"]["review_context_id"]

            code, validated = run_json([
                "validate", target,
                "--result", "still-valid",
                "--reason", "Initial sample baseline is accepted.",
                "--review-context", context,
                "--project-root", str(project),
                "--json",
            ])
            self.assertEqual(code, 0, validated)
            self.assertEqual(validated["data"]["status"], "valid")

            policy = project / "docs/_structured/policies/method_policy.json"
            payload = json.loads(policy.read_text(encoding="utf-8"))
            payload["data"]["allowed_methods"].append("method_c")
            policy.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            code, changed = run_json(["sync", "--project-root", str(project), "--json"])
            self.assertEqual(code, 2, changed)
            code, packet2 = run_json(["explain", target, "--project-root", str(project), "--json"])
            self.assertEqual(code, 2, packet2)
            self.assertEqual(packet2["data"]["computed_status"], "review_required")
            self.assertIn("dependency_changed", packet2["data"]["reason_codes"])
            self.assertNotIn("initial_validation_required", packet2["data"]["reason_codes"])

    def test_authoring_docs_expose_ownership_registration_and_trust_boundaries(self):
        for phrase in (
            "Before editing a visible Markdown file: determine ownership",
            "If `resources` reports the file as plain, run `docengine graph",
            "A Python file existing on disk is not enough",
            "`resources` alone is inventory/ownership information and does **not** prove",
            "Project Python is trusted code, not a sandbox",
            "sync --all` is **not** “force rebuild every valid builder",
        ):
            self.assertIn(phrase, self.workflows)

    def test_workflow_anti_patterns_include_tracking_and_generated_ownership(self):
        self.assertIn("Direct `open()`/network/database read", self.workflows)
        self.assertIn("Editing generated Markdown as canonical", self.workflows)
        self.assertIn("Treating project Python/`verify` as sandboxed", self.workflows)


    def test_clean_chat_quickstart_is_zero_context_entrypoint(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        ai = (ROOT / "docs/AI_USAGE_PROTOCOL.md").read_text(encoding="utf-8")
        repo = (ROOT / "docs/REPOSITORY_WORKFLOW.md").read_text(encoding="utf-8")
        start = (ROOT / "START_HERE_AGENT.md").read_text(encoding="utf-8")

        self.assertIn("docs/CLEAN_CHAT_QUICKSTART.md", readme)
        self.assertLess(readme.index("docs/CLEAN_CHAT_QUICKSTART.md"), readme.index("docs/CORE_WORKFLOWS.md"))
        self.assertIn("CLEAN_CHAT_QUICKSTART.md", ai)
        self.assertIn("CLEAN_CHAT_QUICKSTART.md", repo)
        self.assertIn("docs/CLEAN_CHAT_QUICKSTART.md", start)
        self.assertIn("maintainer/release handoff", start)
        self.assertIn("START_HERE_AGENT.md", quick)
        self.assertIn("Project authoring / using gendocen", quick)
        self.assertIn("Maintaining the gendocen engine itself", quick)

    def test_clean_chat_quickstart_covers_environment_root_trust_and_task_routing(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        for phrase in (
            "python --version",
            "docengine --version",
            "python -m pip install -e .",
            "python -m pip install --no-index dist/generic_documentation_engine-0.1.0.dev22-py3-none-any.whl",
            "--project-root",
            "docengine.toml",
            "Trust preflight before importing project Python",
            "project_package",
            "resources` is suitable for initial resource inventory",
            "proof that a builder is registered",
            "Determine ownership before editing visible Markdown",
            "Default project-authoring loop",
        ):
            self.assertIn(phrase, quick)
        for wf in range(1, 13):
            self.assertRegex(quick, rf"\bWF{wf:02d}\b")
        self.assertIn("FWF01/FWF02", quick)


    def test_clean_chat_quickstart_keeps_explicit_root_in_final_inspection_commands(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        self.assertIn("docengine check --project-root <root> --json", quick)
        self.assertIn("docengine sync --project-root <root> --all --json", quick)

    def test_clean_chat_offline_runtime_fallback_matches_bundled_wheel(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        wheel = ROOT / "dist/generic_documentation_engine-0.1.0.dev22-py3-none-any.whl"
        self.assertTrue(wheel.is_file())
        self.assertIn(f"python -m pip install --no-index dist/{wheel.name}", quick)
        self.assertIn("offline fallback for using the released runtime", quick)

    def test_clean_chat_quickstart_requires_trust_before_extension_loading_commands(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        trust = quick.index("## 4. Trust preflight before importing project Python")
        loop = quick.index("## 7. Default project-authoring loop")
        self.assertLess(trust, loop)
        for command in ("check", "diff", "explain", "graph", "validate", "rebuild", "materialize", "sync", "verify"):
            self.assertRegex(quick[trust:loop], rf"\b{command}\b")
        self.assertRegex(quick, r"not\*\* a security sandbox|not a security sandbox")

    def test_resources_inventory_does_not_import_project_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            (project / "docs/_structured/example").mkdir(parents=True)
            (project / "docengine_project").mkdir()
            (project / "docengine.toml").write_text(
                '[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\n'
                'structured_dir = "_structured"\ndependency_dir = "_dependency"\n'
                'project_package = "docengine_project"\n\n[schemas]\n',
                encoding="utf-8",
            )
            marker = project / "extension-imported.txt"
            (project / "docengine_project/__init__.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('imported', encoding='utf-8')\n"
                "def register_builders(registry):\n    pass\n"
                "def register_semantic_dependencies(registry):\n    pass\n",
                encoding="utf-8",
            )
            (project / "docs/_structured/example/item.json").write_text(
                json.dumps({
                    "$docengine": {"resource_id": "example.item", "materialize": []},
                    "data": {"value": 1},
                }, indent=2) + "\n",
                encoding="utf-8",
            )

            code, resources = run_json(["resources", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0, resources)
            self.assertFalse(marker.exists(), "resources must not import docengine_project in v0.1")

            code, graph = run_json(["graph", "resource://example/item", "--project-root", str(project), "--json"])
            self.assertEqual(code, 0, graph)
            self.assertTrue(marker.exists(), "graph should load the configured project extension")

    def test_zero_context_copyable_project_commands_keep_explicit_root(self):
        paths = (
            ROOT / "README.md",
            ROOT / "docs/CLEAN_CHAT_QUICKSTART.md",
            ROOT / "docs/CORE_WORKFLOWS.md",
            ROOT / "docs/AI_USAGE_PROTOCOL.md",
            ROOT / "examples/product_tax_project/README.md",
            ROOT / "examples/sample_project/README.md",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            rootless = _rootless_zero_context_project_commands(text)
            self.assertEqual(
                rootless,
                [],
                f"rootless project command(s) in {path.relative_to(ROOT)}: {rootless}",
            )

    def test_zero_context_root_guard_splits_compound_shell_commands(self):
        cases = (
            (
                "docengine check --project-root <root> --json && docengine sync --json",
                ["docengine sync --json"],
            ),
            (
                "docengine check --json || docengine sync --project-root <root> --json",
                ["docengine check --json"],
            ),
            (
                "docengine resources --project-root <root> --json; docengine verify --json",
                ["docengine verify --json"],
            ),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(_rootless_zero_context_project_commands(text), expected)

    def test_zero_context_root_guard_catches_plain_imperative_prose(self):
        text = "Temporary probe: Run docengine resources --json now."
        self.assertEqual(
            _rootless_zero_context_project_commands(text),
            ["docengine resources --json now."],
        )

    def test_zero_context_root_guard_accepts_multiline_explicit_root(self):
        text = (
            "docengine validate file://architecture/rationale.md " + "\\\n"
            + "  --project-root <root> " + "\\\n"
            + "  --result still-valid --json"
        )
        self.assertEqual(_rootless_zero_context_project_commands(text), [])


    def test_zero_context_root_guard_rejects_root_option_only_in_shell_comment(self):
        text = "docengine sync --json # TODO add --project-root <root>"
        self.assertEqual(
            _rootless_zero_context_project_commands(text),
            ["docengine sync --json # TODO add --project-root <root>"],
        )

    def test_zero_context_root_guard_rejects_root_text_only_inside_quoted_value(self):
        text = 'docengine validate file://architecture/rationale.md --reason "mention --project-root here" --json'
        self.assertEqual(
            _rootless_zero_context_project_commands(text),
            [text],
        )

    def test_zero_context_root_guard_accepts_equals_form_option(self):
        text = "docengine resources --project-root=<root> --json"
        self.assertEqual(_rootless_zero_context_project_commands(text), [])

    def test_zero_context_root_guard_rejects_empty_or_value_masquerading_root_options(self):
        cases = (
            'docengine sync --project-root= --json',
            'docengine sync --project-root "" --json',
            'docengine sync --project-root --json',
            'docengine validate file://x --reason "--project-root" --json',
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(_rootless_zero_context_project_commands(text), [text])

    def test_zero_context_root_guard_splits_pipe_and_background_operators(self):
        cases = (
            ("docengine check --json | docengine sync --project-root <root> --json", ["docengine check --json"]),
            ("docengine check --json & docengine sync --project-root <root> --json", ["docengine check --json"]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(_rootless_zero_context_project_commands(text), expected)

    def test_fixture_dot_root_is_only_used_after_fixture_cwd_is_established(self):
        fixtures = (
            (ROOT / "examples/product_tax_project/README.md", "cd /tmp/gendocen-product-tax"),
            (ROOT / "examples/sample_project/README.md", "cd /tmp/gendocen-sample"),
        )
        for path, cd_command in fixtures:
            lines = path.read_text(encoding="utf-8").splitlines()
            first_dot_root = next(i for i, line in enumerate(lines) if "--project-root ." in line)
            cd_index = next(i for i, line in enumerate(lines) if line.strip() == cd_command)
            self.assertLess(
                cd_index,
                first_dot_root,
                f"{path.relative_to(ROOT)} uses --project-root . before establishing fixture cwd",
            )

    def test_active_documentation_identity_is_synchronized_through_v039(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = (ROOT / "START_HERE_AGENT.md").read_text(encoding="utf-8")
        workflow = (ROOT / "docs/REPOSITORY_WORKFLOW.md").read_text(encoding="utf-8")
        system_map = (ROOT / "docs/SYSTEM_MAP.md").read_text(encoding="utf-8")
        file_map = (ROOT / "plan/FILE_MAP.md").read_text(encoding="utf-8")
        release_gate = (ROOT / "docs/RELEASE_GATE.md").read_text(encoding="utf-8")
        self.assertIn("v0.39 project-config root-policy sync", readme)
        self.assertIn("0.39.0-p8-project-config-root-policy-sync", readme)
        self.assertIn("v0.39 project-config root-policy sync", start)
        self.assertIn("handoff-v0.39.0", workflow)
        self.assertIn("Project-config root-policy sync (v0.39)", system_map)
        self.assertIn("v0.39 project-config root-policy sync artifacts", file_map)
        self.assertIn("0.39.0-p8-project-config-root-policy-sync", release_gate)

    def test_project_config_reference_matches_explicit_root_policy(self):
        config = (ROOT / "docs/PROJECT_CONFIG.md").read_text(encoding="utf-8")
        self.assertIn("Explicit string overrides for both `--project-root` and `--docs-root` must be non-empty and non-whitespace", config)
        self.assertIn("usage/config errors (exit `4` at the CLI boundary)", config)
        self.assertIn("Explicit `--docs-root .` remains a valid deliberate override", config)
        self.assertIn("may be absent for an empty/uninitialized documentation tree", config)

    def test_wf03_preserves_exact_baseline_addition_example(self):
        workflows = (ROOT / "docs/CORE_WORKFLOWS.md").read_text(encoding="utf-8")
        self.assertIn("field1 = A.field3 + B.field2", workflows)
        self.assertIn('result["field1"] = result["field3"] + b2', workflows)
        self.assertNotIn("field1 = A.field3 * B.field2", workflows)

    def test_wf03_fresh_project_minimal_envelopes_build_invalidate_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fresh"
            root.mkdir()
            code, initialized = run_json(["init", "--project-root", str(root), "--json"])
            self.assertEqual(code, 0, initialized)
            structured = root / "docs/_structured/example"
            structured.mkdir(parents=True)
            a = {"$docengine": {"resource_id": "example.a", "materialize": []}, "data": {"field3": 10, "description": "A"}}
            b = {"$docengine": {"resource_id": "example.b", "materialize": []}, "data": {"field2": 5, "unrelated": "not used"}}
            c = {"$docengine": {"resource_id": "example.c", "resource_kind": "derived_descriptor", "materialize": [{"renderer": "markdown", "path": "example/c.md", "path_base": "documentation_root"}]}, "data": {}}
            for name, payload in (("a", a), ("b", b), ("c", c)):
                (structured / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            pkg = root / "docengine_project/builders/example"
            pkg.mkdir(parents=True)
            (root / "docengine_project/__init__.py").write_text("def register_builders(registry):\n    from .builders import register\n    register(registry)\n", encoding="utf-8")
            (root / "docengine_project/builders/__init__.py").write_text("from .example.c import register as register_c\n\ndef register(registry):\n    register_c(registry)\n", encoding="utf-8")
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / "c.py").write_text(
                "def build_c(ctx):\n"
                "    a = ctx.get('resource://example/a')\n"
                "    b2 = ctx.read('resource://example/b#/field2')\n"
                "    result = dict(a.to_builtin())\n"
                "    result['field1'] = result['field3'] + b2\n"
                "    return result\n\n"
                "def register(registry):\n"
                "    registry.register('resource://example/c', build_c, builder_id='example.c', dependency_type='compute', comparator='exact')\n",
                encoding="utf-8",
            )
            code, synced = run_json(["sync", "--project-root", str(root), "--json"])
            self.assertEqual(code, 0, synced)
            code, graph = run_json(["graph", "resource://example/c", "--project-root", str(root), "--json"])
            self.assertEqual(code, 0, graph)
            self.assertIn("resource://example/a", json.dumps(graph))
            self.assertIn("resource://example/b#/field2", json.dumps(graph))
            b["data"]["field2"] = 7
            (structured / "b.json").write_text(json.dumps(b, indent=2) + "\n", encoding="utf-8")
            code, checked = run_json(["check", "--project-root", str(root), "--json"])
            self.assertEqual(code, 2, checked)
            self.assertIn("build_required", json.dumps(checked))
            code, synced2 = run_json(["sync", "--project-root", str(root), "--json"])
            self.assertEqual(code, 0, synced2)
            code, verified = run_json(["verify", "--project-root", str(root), "--json"])
            self.assertEqual(code, 0, verified)
            self.assertIn("17", (root / "docs/example/c.md").read_text(encoding="utf-8"))

    def test_all_core_workflows_meet_v036_semantic_scenario_minimum(self):
        workflows = (ROOT / "docs/CORE_WORKFLOWS.md").read_text(encoding="utf-8")
        headings = list(re.finditer(r"^## (WF\d{2})\b", workflows, re.MULTILINE))
        self.assertEqual([m.group(1) for m in headings], [f"WF{i:02d}" for i in range(1, 13)])
        for i, match in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else workflows.index("# Future authoring helpers")
            section = workflows[match.start():end]
            with self.subTest(workflow=match.group(1)):
                self.assertIn("**Actor:**", section)
                self.assertIn("**Goal:**", section)
                self.assertRegex(section, r"\*\*Atomic contracts?:\*\*")
                self.assertIn("**Operational path:**", section)
                self.assertIn("**Observable result:**", section)
        amendment = (ROOT / "plan/WORKFLOW_SCENARIO_TEMPLATE_BASELINE_AMENDMENT.md").read_text(encoding="utf-8")
        self.assertIn("Additive refinement only", amendment)
        self.assertIn("historical pre-work baseline remains unchanged", amendment)

    def test_explicit_root_remains_authoritative_when_cwd_is_another_project(self):
        source = ROOT / "examples/product_tax_project"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_a = tmp_path / "project-a"
            project_b = tmp_path / "project-b"
            shutil.copytree(source, project_a)
            shutil.copytree(source, project_b)

            # Make B visibly unsafe to import: any accidental graph/check/sync/verify
            # against cwd instead of explicit A will create this marker.
            marker_b = project_b / "WRONG_PROJECT_IMPORTED.txt"
            init_b = project_b / "docengine_project/__init__.py"
            init_b.write_text(
                "from pathlib import Path\n"
                + f"Path({str(marker_b)!r}).write_text('wrong project imported', encoding='utf-8')\n"
                + init_b.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            product = project_a / "docs/_structured/catalog/product.json"
            payload = json.loads(product.read_text(encoding="utf-8"))
            payload["data"]["price"] = 125
            product.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            def snapshot(root):
                return {
                    path.relative_to(root).as_posix(): path.read_bytes()
                    for path in root.rglob("*")
                    if path.is_file()
                }

            before_b = snapshot(project_b)
            old_cwd = Path.cwd()
            try:
                os.chdir(project_b)

                code, resources = run_json(["resources", "--project-root", str(project_a), "--json"])
                self.assertEqual(code, 0, resources)
                self.assertEqual(Path(resources["data"]["roots"]["project_root"]), project_a.resolve())

                code, graph = run_json([
                    "graph", "resource://catalog/price_with_tax",
                    "--project-root", str(project_a), "--json",
                ])
                self.assertEqual(code, 0, graph)

                code, checked = run_json(["check", "--project-root", str(project_a), "--json"])
                self.assertEqual(code, 2, checked)

                code, synced = run_json(["sync", "--project-root", str(project_a), "--json"])
                self.assertEqual(code, 0, synced)

                code, verified = run_json(["verify", "--project-root", str(project_a), "--json"])
                self.assertEqual(code, 0, verified)
            finally:
                os.chdir(old_cwd)

            generated_a = (project_a / "docs/catalog/price_with_tax.md").read_text(encoding="utf-8")
            self.assertIn("**Price:** 125", generated_a)
            self.assertFalse(marker_b.exists(), "explicit-root commands must not import cwd project B")
            self.assertEqual(snapshot(project_b), before_b, "explicit-root sequence must not mutate cwd project B")

    def test_empty_explicit_root_fails_closed_in_wrong_cwd_without_mutation(self):
        source = ROOT / "examples/product_tax_project"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "cwd-project"
            shutil.copytree(source, project)
            product = project / "docs/_structured/catalog/product.json"
            payload = json.loads(product.read_text(encoding="utf-8"))
            payload["data"]["price"] = 137
            product.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            generated = project / "docs/catalog/price_with_tax.md"
            before = generated.read_bytes()
            old_cwd = Path.cwd()
            try:
                os.chdir(project)
                code, result = run_json(["sync", "--project-root", "", "--json"])
            finally:
                os.chdir(old_cwd)
            self.assertEqual(code, 4, result)
            self.assertFalse(result["ok"])
            self.assertIn("must not be empty", json.dumps(result))
            self.assertEqual(generated.read_bytes(), before, "empty explicit root must fail before cwd mutation")

    def test_empty_explicit_docs_root_fails_closed_and_cannot_false_verify(self):
        source = ROOT / "examples/product_tax_project"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(source, project)
            generated = project / "docs/catalog/price_with_tax.md"
            generated.write_text(generated.read_text(encoding="utf-8") + "\nDRIFT\n", encoding="utf-8")

            code, normal_verify = run_json(["verify", "--project-root", str(project), "--json"])
            self.assertEqual(code, 3, normal_verify)
            self.assertFalse(normal_verify["ok"])

            root_state = project / "_dependency"
            self.assertFalse(root_state.exists())
            before = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in project.rglob("*")
                if path.is_file()
            }

            for command in ("resources", "sync", "verify"):
                with self.subTest(command=command):
                    code, result = run_json([command, "--project-root", str(project), "--docs-root", "", "--json"])
                    self.assertEqual(code, 4, result)
                    self.assertFalse(result["ok"])
                    self.assertIn("documentation root must not be empty", json.dumps(result))
                    self.assertFalse(root_state.exists(), "empty docs root must fail before root-level runtime state is created")

            after = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in project.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before, "empty docs root must fail before project mutation")

    def test_explicit_init_creates_nested_intended_project_instead_of_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "parent"
            child = parent / "child-new"
            parent.mkdir()
            child.mkdir()
            code, initialized_parent = run_json(["init", "--project-root", str(parent), "--json"])
            self.assertEqual(code, 0, initialized_parent)
            self.assertTrue((parent / "docengine.toml").is_file())

            old_cwd = Path.cwd()
            try:
                os.chdir(child)
                code, initialized_child = run_json(["init", "--project-root", str(child), "--json"])
                self.assertEqual(code, 0, initialized_child)
            finally:
                os.chdir(old_cwd)

            self.assertEqual(Path(initialized_child["data"]["roots"]["project_root"]), child.resolve())
            self.assertTrue((child / "docengine.toml").is_file())

    def test_quickstart_distinguishes_project_root_from_docs_root(self):
        quick = (ROOT / "docs/CLEAN_CHAT_QUICKSTART.md").read_text(encoding="utf-8")
        self.assertIn("Project-root discovery precedence", quick)
        self.assertIn("`--docs-root` does **not** select a project", quick)
        self.assertIn("Explicit `--project-root` and explicit `--docs-root` values must both be non-empty", quick)
        self.assertIn("docengine init --project-root /path/to/intended/project --json", quick)


if __name__ == "__main__":
    unittest.main()
