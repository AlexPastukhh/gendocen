#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import json, hashlib, sys, tomllib, zipfile
try:
    import jsonschema
except Exception as e:
    print(f"FAIL: jsonschema required for spec audit: {e}")
    sys.exit(5)
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def j(rel):
    try: return json.loads((ROOT/rel).read_text(encoding="utf-8"))
    except Exception as e: errors.append(f"JSON parse {rel}: {e}"); return None
# Parse all JSON.
for p in ROOT.rglob('*.json'):
    try: json.loads(p.read_text(encoding="utf-8"))
    except Exception as e: errors.append(f"JSON parse {p.relative_to(ROOT)}: {e}")
# Schema validations.
for schema_path in sorted((ROOT/'spec/schemas').glob('*.json')):
    try: jsonschema.Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))
    except Exception as e: errors.append(f"invalid JSON Schema {schema_path.relative_to(ROOT)}: {getattr(e,'message',e)}")

def validate(schema_rel, paths):
    schema=j(schema_rel)
    if not schema: return
    for p in paths:
        try: jsonschema.validate(json.loads(p.read_text(encoding="utf-8")), schema)
        except Exception as e: errors.append(f"schema {p.relative_to(ROOT)} vs {schema_rel}: {e.message if hasattr(e,'message') else e}")
validate('spec/schemas/PHASE_EXECUTION_RECORD.schema.json', sorted((ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json')))
validate('spec/schemas/USE_CASE_REGISTRY.schema.json', [ROOT/'spec/registries/USE_CASE_REGISTRY.json'])
validate('spec/schemas/MANAGED_RESOURCE.schema.json', sorted((ROOT/'examples').glob('*/docs/_structured/**/*.json')))
validate('spec/schemas/DEPENDENCY_STATE.schema.json', sorted((ROOT/'examples').glob('*/docs/_dependency/state/dependency_state.json')))
validate('spec/schemas/MATERIALIZATION_STATE.schema.json', sorted((ROOT/'examples').glob('*/docs/_dependency/state/materialization_state.json')))
validate('spec/schemas/RUNTIME_LAYOUT.schema.json', sorted((ROOT/'examples').glob('*/docs/_dependency/hardening/runtime_layout.json')))
validate('spec/schemas/PERFORMANCE_BUDGET.schema.json', [ROOT/'spec/release/PERFORMANCE_BUDGET.json'])
validate('spec/schemas/PERFORMANCE_GATE.schema.json', [ROOT/'plan/evidence/P8/performance_gate.json'] if (ROOT/'plan/evidence/P8/performance_gate.json').exists() else [])
validate('spec/schemas/DEPENDENCY_RECEIPT.schema.json', sorted((ROOT/'examples').glob('*/docs/_dependency/receipts/*.json')))
validate('spec/schemas/BASELINE_SNAPSHOT.schema.json', sorted((ROOT/'examples').glob('*/docs/_dependency/baselines/*.json')))
review_schema=j('spec/schemas/REVIEW_PACKET.schema.json')
if review_schema:
    for rp in sorted((ROOT/'plan/evidence/P4').glob('*review_packet.json')) if (ROOT/'plan/evidence/P4').exists() else []:
        try: jsonschema.validate(json.loads(rp.read_text(encoding="utf-8")), review_schema)
        except Exception as e: errors.append(f"schema {rp.relative_to(ROOT)} vs REVIEW_PACKET: {e.message if hasattr(e,'message') else e}")
# JSONL dependency events are schema-validated line by line.
event_schema=j('spec/schemas/DEPENDENCY_EVENT.schema.json')
if event_schema:
    for ep in sorted((ROOT/'examples').glob('*/docs/_dependency/events/dependency_events.jsonl')):
        for lineno,line in enumerate(ep.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip(): continue
            try: jsonschema.validate(json.loads(line), event_schema)
            except Exception as e: errors.append(f"schema {ep.relative_to(ROOT)} line {lineno} vs DEPENDENCY_EVENT: {e.message if hasattr(e,'message') else e}")
migration_event_schema=j('spec/schemas/HARDENING_MIGRATION_EVENT.schema.json')
if migration_event_schema:
    for ep in sorted((ROOT/'examples').glob('*/docs/_dependency/hardening/migration_events.jsonl')):
        for lineno,line in enumerate(ep.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip(): continue
            try: jsonschema.validate(json.loads(line), migration_event_schema)
            except Exception as e: errors.append(f"schema {ep.relative_to(ROOT)} line {lineno} vs HARDENING_MIGRATION_EVENT: {e.message if hasattr(e,'message') else e}")
recovery_event_schema=j('spec/schemas/HARDENING_RECOVERY_EVENT.schema.json')
if recovery_event_schema:
    for ep in sorted((ROOT/'examples').glob('*/docs/_dependency/hardening/recovery_events.jsonl')):
        for lineno,line in enumerate(ep.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip(): continue
            try: jsonschema.validate(json.loads(line), recovery_event_schema)
            except Exception as e: errors.append(f"schema {ep.relative_to(ROOT)} line {lineno} vs HARDENING_RECOVERY_EVENT: {e.message if hasattr(e,'message') else e}")
axes=j('spec/registries/ACCEPTANCE_AXES.json') or {'axes':[]}
axis_ids={a['id'] for a in axes['axes']}; release_axes={a['id'] for a in axes['axes'] if a.get('release_gate')}
# Phase consistency.
coverage=[]
for p in sorted((ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json')):
    d=json.loads(p.read_text(encoding="utf-8")); pid=d['phase_id']; mapped=set(d['acceptance_axes']); coverage += d.get('use_cases',[])
    crit=set(a for c in d['acceptance_criteria'] for a in c['axis_ids'])
    if not crit <= mapped: errors.append(f"{pid}: criterion axes not declared at phase: {sorted(crit-mapped)}")
    if not mapped <= axis_ids: errors.append(f"{pid}: unknown axes: {sorted(mapped-axis_ids)}")
    ar={x['axis_id'] for x in d['axis_reviews']}
    if ar != mapped: errors.append(f"{pid}: axis review slots mismatch mapped axes")
    pending=[q['id'] for k in ('pre_execution_questions','emergent_questions') for q in d[k] if q['blocking'] and q['status']!='answered']
    if pending != d['acceptance_summary']['unresolved_blocking_questions']:
        errors.append(f"{pid}: unresolved blocking summary mismatch {pending} vs {d['acceptance_summary']['unresolved_blocking_questions']}")
# No unresolved user-owned pre-execution questions remain before implementation.
for p in sorted((ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json')):
    d=json.loads(p.read_text(encoding="utf-8"))
    pending_user=[q['id'] for k in ('pre_execution_questions','emergent_questions') for q in d[k] if q.get('owner')=='user' and q['status']!='answered']
    if pending_user: errors.append(f"{d['phase_id']}: unresolved user questions before implementation: {pending_user}")
# Canonical global phase/axis consistency, carried-release-gate semantics and
# path-like evidence-reference integrity are enforced by the release auditor too.
try:
    audit_spec = importlib.util.spec_from_file_location('docengine_audit_axes', ROOT/'tools/audit_axes.py')
    audit_mod = importlib.util.module_from_spec(audit_spec)
    assert audit_spec and audit_spec.loader
    audit_spec.loader.exec_module(audit_mod)
    axis_result = audit_mod.audit(ROOT)
    if not axis_result.get('ok'):
        for finding in axis_result.get('findings', []):
            errors.append(f"global axis audit: {finding}")
except Exception as e:
    errors.append(f"global axis audit integration failed: {e}")

# If the repository uses carried release gates, both schema and declared
# acceptance rule must describe them explicitly.
phase_schema = j('spec/schemas/PHASE_EXECUTION_RECORD.schema.json')
if phase_schema:
    carried_prop = phase_schema.get('properties', {}).get('carried_release_gates')
    if not carried_prop:
        errors.append('phase execution schema missing carried_release_gates')
if any(json.loads(p.read_text(encoding="utf-8")).get('carried_release_gates') for p in sorted((ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json'))):
    rule = (axes.get('acceptance_rule') or '') if isinstance(axes, dict) else ''
    if 'carried_release_gate' not in rule:
        errors.append('acceptance rule does not describe carried_release_gate semantics')

# Verify semantics are explicit: report always, failed verification is status not crash.
p8_tmp=json.loads((ROOT/'plan/phase_records/P8_EXECUTION_RECORD.json').read_text(encoding="utf-8"))
q81=next((q for q in p8_tmp['pre_execution_questions'] if q['id']=='Q8.1'), None)
if not q81 or q81.get('status')!='answered' or 'ok=false' not in (q81.get('decision') or ''):
    errors.append('Q8.1 verify semantics not fully resolved')

# Final release sequencing and global gates.
p7=j('plan/phase_records/P7_EXECUTION_RECORD.json'); p8=j('plan/phase_records/P8_EXECUTION_RECORD.json')
if p7 and 'DAX15' not in p7['acceptance_axes']: errors.append('P7 hardening must cover DAX15 before release')
if p8 and not release_axes <= set(p8['acceptance_axes']): errors.append(f"P8 missing release-gate axes: {sorted(release_axes-set(p8['acceptance_axes']))}")
if p8 and p8.get('status')=='accepted':
    p8_reviews={a['axis_id']:a for a in p8.get('axis_reviews',[])}
    required_release=set(release_axes)|{'DAX18'}
    bad={axis:p8_reviews.get(axis,{}).get('status') for axis in required_release if p8_reviews.get(axis,{}).get('status')!='pass'}
    if bad: errors.append(f"P8 accepted with unclosed release axes: {bad}")
    bad_criteria=[c['id'] for c in p8.get('acceptance_criteria',[]) if c.get('status')!='pass']
    if bad_criteria: errors.append(f"P8 accepted with non-pass criteria: {bad_criteria}")
    perf=j('plan/evidence/P8/performance_gate.json')
    if not perf or perf.get('ok') is not True: errors.append('P8 accepted without passing performance gate evidence')
# Use-case coverage and CLI references.
uc=j('spec/registries/USE_CASE_REGISTRY.json'); cli=j('spec/registries/CLI_COMMANDS.json')
if uc and cli:
    cmds=set(cli['commands']); ids=[u['id'] for u in uc['use_cases']]
    if cli.get('machine_output_schema_version') != '2.0.0': errors.append(f"CLI registry machine schema mismatch: {cli.get('machine_output_schema_version')}")
    if set(cli.get('exit_codes', {})) != {'0','2','3','4','5'}: errors.append(f"CLI exit-code registry mismatch: {sorted(cli.get('exit_codes', {}))}")
    if len(ids)!=len(set(ids)): errors.append('duplicate use case ids')
    v01={u['id'] for u in uc['use_cases'] if u['implementation_target']=='v0.1'}
    missing=v01-set(coverage)
    if missing: errors.append(f"v0.1 use cases not mapped to any phase: {sorted(missing)}")
    for u in uc['use_cases']:
        bad=set(u['cli_commands'])-cmds
        if bad: errors.append(f"{u['id']} references unknown CLI commands {sorted(bad)}")
# Status vocabulary consistency.
ds=j('spec/schemas/DEPENDENCY_STATE.schema.json')
if ds:
    vals=ds['properties']['targets']['additionalProperties']['properties']['status']['enum']
    if 'build_required' not in vals or 'rebuild_required' in vals: errors.append(f"dependency status vocabulary mismatch: {vals}")
# Example generated paths are docs-root-relative and derived descriptor exists.
for p in (ROOT/'examples/sample_project/docs/_structured').rglob('*.json'):
    d=json.loads(p.read_text(encoding="utf-8"))
    for m in d.get('$docengine',{}).get('materialize',[]):
        if m.get('path_base')!='documentation_root': errors.append(f"{p.relative_to(ROOT)} materialize path_base must be documentation_root")
        q=Path(m['path'])
        if q.is_absolute() or '..' in q.parts: errors.append(f"unsafe materialize path in {p.relative_to(ROOT)}: {m['path']}")

# Runtime/distribution identity consistency.
try:
    pyproject = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
    project_version = pyproject['project']['version']
except Exception as e:
    errors.append(f"pyproject version parse failed: {e}")
    project_version = None

engine_version = None
machine_output_schema_version = None
runtime_layout_version = None
try:
    ns = {}
    exec((ROOT/'src/docengine/versions.py').read_text(encoding='utf-8'), ns)
    engine_version = ns.get('ENGINE_VERSION')
    machine_output_schema_version = ns.get('MACHINE_OUTPUT_SCHEMA_VERSION')
    runtime_layout_version = ns.get('RUNTIME_LAYOUT_VERSION')
except Exception as e:
    errors.append(f"engine version parse failed: {e}")

if project_version and engine_version and project_version != engine_version:
    errors.append(f"runtime version mismatch pyproject={project_version} engine={engine_version}")

if machine_output_schema_version:
    cli_schema=j('spec/schemas/CLI_OUTPUT.schema.json')
    if cli_schema and cli_schema.get('properties',{}).get('schema_version',{}).get('const') != machine_output_schema_version:
        errors.append('CLI_OUTPUT schema version does not match runtime MACHINE_OUTPUT_SCHEMA_VERSION')
    cli_registry=j('spec/registries/CLI_COMMANDS.json')
    if cli_registry and cli_registry.get('machine_output_schema_version') != machine_output_schema_version:
        errors.append('CLI command registry machine schema version does not match runtime')

if runtime_layout_version:
    layout_schema=j('spec/schemas/RUNTIME_LAYOUT.schema.json')
    if layout_schema and layout_schema.get('properties',{}).get('runtime_layout_version',{}).get('const') != runtime_layout_version:
        errors.append('RUNTIME_LAYOUT schema version does not match runtime RUNTIME_LAYOUT_VERSION')
    if layout_schema:
        try:
            jsonschema.validate({'runtime_layout_version': runtime_layout_version}, layout_schema)
        except jsonschema.ValidationError:
            pass
        else:
            errors.append('RUNTIME_LAYOUT schema incorrectly accepts marker without initialization/migration provenance')
    migration_registry=j('spec/registries/MIGRATIONS.json')
    if migration_registry and migration_registry.get('runtime_layout_version') != runtime_layout_version:
        errors.append('migration registry runtime layout version does not match runtime')
    if migration_registry:
        ids=[m.get('migration_id') for m in migration_registry.get('migrations',[])]
        if len(ids)!=len(set(ids)): errors.append('duplicate migration ids')
        expected = next((m for m in migration_registry.get('migrations',[]) if m.get('migration_id') == 'p6-unmarked-to-runtime-layout-1'), None)
        if not expected or expected.get('from_version') != 'legacy-p6-unmarked' or expected.get('to_version') != runtime_layout_version or expected.get('preserves_released_evidence') is not True:
            errors.append('required P6->P7 migration registry entry missing or inconsistent')
    tx_schema=j('spec/schemas/TRANSACTION_JOURNAL.schema.json')
    if tx_schema:
        props=tx_schema.get('properties',{})
        if props.get('journal_schema_version',{}).get('const') != '1.0.0' or 'transaction_id' not in props or 'operations' not in props:
            errors.append('TRANSACTION_JOURNAL schema missing required identity/operations contract')
    recovery_schema=j('spec/schemas/HARDENING_RECOVERY_EVENT.schema.json')
    migration_event_schema2=j('spec/schemas/HARDENING_MIGRATION_EVENT.schema.json')
    if recovery_schema and recovery_schema.get('additionalProperties') is not False:
        errors.append('HARDENING_RECOVERY_EVENT must reject unknown fields')
    if migration_event_schema2 and migration_event_schema2.get('additionalProperties') is not False:
        errors.append('HARDENING_MIGRATION_EVENT must reject unknown fields')

# Active handoff docs must describe the current runtime rather than a prior accepted build.
if engine_version:
    for rel in ('README.md', 'START_HERE_AGENT.md', 'plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md'):
        text = (ROOT/rel).read_text(encoding='utf-8')
        if engine_version not in text:
            errors.append(f"active handoff doc does not name current runtime {engine_version}: {rel}")
ai_protocol=(ROOT/'docs/AI_USAGE_PROTOCOL.md').read_text(encoding='utf-8')
if 'Current P1 boundary' in ai_protocol or 'current boundary is P1' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P1')
if 'current boundary is P2' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P2')
if 'Current P3 boundary' in ai_protocol or 'current boundary is P3' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P3 after P4 acceptance')
if 'Current P4 boundary' in ai_protocol or 'current boundary is P4' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P4 after P5 acceptance')
if 'Current P5 boundary' in ai_protocol or 'current boundary is P5' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P5 after P6 acceptance')
if 'Current P6 boundary' in ai_protocol or 'current boundary is P6' in ai_protocol:
    errors.append('AI_USAGE_PROTOCOL still describes the current boundary as P6 after P7 acceptance')
if 'file://docs/' in (ROOT/'docs/DEPENDENCY_MODEL.md').read_text(encoding='utf-8'):
    errors.append('DEPENDENCY_MODEL contains non-canonical file://docs/ refs; file refs are documentation-root-relative')
materialization_runtime=(ROOT/'docs/MATERIALIZATION_RUNTIME.md').read_text(encoding='utf-8')
if 'verify` remains P8/release-gate work and is intentionally not implemented yet' in materialization_runtime:
    errors.append('MATERIALIZATION_RUNTIME still claims verify is unimplemented after P6 acceptance')
hardening_runtime=(ROOT/'docs/HARDENING_RUNTIME.md').read_text(encoding='utf-8')
if 'P7' not in hardening_runtime or 'recover --force' not in hardening_runtime:
    errors.append('HARDENING_RUNTIME does not describe active P7 recovery contract')
for rel in ('docs/MATERIALIZATION_RUNTIME.md','src/docengine/README.md','src/docengine/cli.py'):
    text=(ROOT/rel).read_text(encoding='utf-8')
    if 'Implemented through P6' in text or 'complete through P6' in text:
        errors.append(f'active P7 source/doc still describes implementation as through P6: {rel}')
if p8 and p8.get('status')=='accepted':
    for rel in ('README.md','START_HERE_AGENT.md','docs/SYSTEM_MAP.md','src/docengine/README.md'):
        text=(ROOT/rel).read_text(encoding='utf-8')
        if 'P8 planned' in text or 'next phase: `P8' in text or 'through **P7' in text or 'through P7' in text:
            errors.append(f'active final handoff still describes P8 as future/P7 as current: {rel}')
    # Historical P7 handoff must also reflect its completed package gate while
    # preserving the historical DAX18 partial through a formal carried gate.
    p7_accept=(ROOT/'plan/P7_ACCEPTANCE_REVIEW.md').read_text(encoding='utf-8')
    if 'ACCEPTANCE CANDIDATE' in p7_accept or 'package gate pending' in p7_accept:
        errors.append('P7 acceptance review still describes a pending package gate after P8 acceptance')
    p7_axis=(ROOT/'plan/P7_AXIS_AUDIT.md').read_text(encoding='utf-8')
    if 'DAX20 pending' in p7_axis.lower() or '| DAX20 Release/handoff integrity | PENDING' in p7_axis:
        errors.append('P7 axis audit still describes DAX20 as pending after P8 acceptance')
    impl=(ROOT/'plan/IMPLEMENTATION_PLAN.md').read_text(encoding='utf-8')
    p7_start=impl.find('## P7 —')
    p8_start=impl.find('## P8 —')
    p7_slice=impl[p7_start:p8_start if p8_start!=-1 else None] if p7_start!=-1 else ''
    if 'acceptance_review' in p7_slice or 'package gate pending' in p7_slice:
        errors.append('implementation plan still describes P7 as acceptance_review/pending after P8 acceptance')
    oq=(ROOT/'OPEN_QUESTIONS_AND_AMBIGUITIES.md').read_text(encoding='utf-8')
    if 'before P7' in oq:
        errors.append('open-question index still describes current blockers relative to P7 after final P8 release')
    if 'WATCH ITEM / P8 portability clarification' in oq or 'Recommended P8 closure' in oq:
        errors.append('open-question index leaves A7 as future P8 work after P8 acceptance')
    if 'DAX18 remains partial by design' in oq:
        errors.append('open-question index still describes DAX18 as unresolved after P8 acceptance')
    if p7:
        dax20=next((a for a in p7.get('axis_reviews',[]) if a.get('axis_id')=='DAX20'),None)
        if dax20 and dax20.get('status')=='pass' and any('pending' in f.lower() for f in dax20.get('findings',[])):
            errors.append('P7 DAX20 PASS still contains pending findings')

    # The documented performance command must be self-contained for source handoff.
    bench=(ROOT/'tools/benchmark_release.py').read_text(encoding='utf-8')
    if "PYTHONPATH" not in bench or "ROOT/'src'" not in bench:
        errors.append('benchmark_release.py does not make src/ importable for its benchmark subprocess')

wheels = sorted((ROOT/'dist').glob('*.whl')) if (ROOT/'dist').exists() else []
if len(wheels) != 1:
    errors.append(f"active dist must contain exactly one current wheel, found {[p.name for p in wheels]}")
elif engine_version:
    wheel = wheels[0]
    expected_token = engine_version.replace('-', '_')
    if expected_token not in wheel.name:
        errors.append(f"active wheel filename does not match engine version {engine_version}: {wheel.name}")
    try:
        with zipfile.ZipFile(wheel) as zf:
            metadata_names = [n for n in zf.namelist() if n.endswith('.dist-info/METADATA')]
            if len(metadata_names) != 1:
                errors.append(f"wheel metadata entry count invalid: {metadata_names}")
            else:
                metadata = zf.read(metadata_names[0]).decode('utf-8', errors='replace')
                version_lines = [line.split(':',1)[1].strip() for line in metadata.splitlines() if line.startswith('Version:')]
                if version_lines != [engine_version]:
                    errors.append(f"wheel metadata version mismatch: {version_lines} vs {engine_version}")
    except Exception as e:
        errors.append(f"active wheel integrity failed: {e}")

    # The active wheel must contain the same runtime Python sources as src/docengine.
    try:
        with zipfile.ZipFile(wheel) as zf:
            wheel_py = {n: zf.read(n) for n in zf.namelist() if n.startswith('docengine/') and n.endswith('.py')}
        src_py = {f'docengine/{p.name}': p.read_bytes() for p in (ROOT/'src/docengine').glob('*.py')}
        if set(wheel_py) != set(src_py):
            errors.append(f"wheel/source module set mismatch missing={sorted(set(src_py)-set(wheel_py))} extra={sorted(set(wheel_py)-set(src_py))}")
        else:
            for name, data in src_py.items():
                if hashlib.sha256(wheel_py[name]).hexdigest() != hashlib.sha256(data).hexdigest():
                    errors.append(f"wheel/source content mismatch: {name}")
    except Exception as e:
        errors.append(f"wheel/source parity check failed: {e}")

# Build intermediates are not part of a transferable release package.
if (ROOT/'build').exists():
    errors.append('transient build/ directory must be removed before package verification')

# Repository persistence controls are part of the v0.26 handoff. Git internals are not.
required_repo_files = (
    '.gitignore', '.gitattributes', '.editorconfig',
    '.github/workflows/ci.yml', '.github/workflows/release-gate.yml',
    'docs/REPOSITORY_WORKFLOW.md', 'plan/REPOSITORY_PERSISTENCE_AUDIT.md',
    'plan/WINDOWS_REPOSITORY_PORTABILITY_AUDIT.md',
)
for rel in required_repo_files:
    if not (ROOT/rel).is_file():
        errors.append(f'repository persistence file missing: {rel}')
gitignore = (ROOT/'.gitignore').read_text(encoding='utf-8') if (ROOT/'.gitignore').is_file() else ''
for required in ('__pycache__/', '.pytest_cache/', 'build/', '*.egg-info/', '.venv/'):
    if required not in gitignore:
        errors.append(f'.gitignore missing required transient pattern: {required}')
for line in gitignore.splitlines():
    stripped=line.strip()
    if stripped and not stripped.startswith('#') and stripped.rstrip('/') == 'dist':
        errors.append('dist/ must remain tracked; .gitignore must not ignore it')
ci_text=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8') if (ROOT/'.github/workflows/ci.yml').is_file() else ''
for command in ('python -m pytest -q','python tools/audit_spec.py','python tools/audit_axes.py --json','python tools/release_manifest.py validate --json','python tools/release_check.py --json'):
    if command not in ci_text:
        errors.append(f'CI workflow missing required repository check: {command}')
if not all(token in ci_text for token in ("'git'", "'status'", "'--porcelain'")):
    errors.append('CI workflow missing portable git status --porcelain cleanliness check')
if 'windows-latest' not in ci_text or "'3.14'" not in ci_text:
    errors.append('CI workflow missing Windows/Python 3.14 repository regression job')
release_ci=(ROOT/'.github/workflows/release-gate.yml').read_text(encoding='utf-8') if (ROOT/'.github/workflows/release-gate.yml').is_file() else ''
if 'python tools/benchmark_release.py --json' not in release_ci:
    errors.append('release-gate workflow missing performance benchmark command')
if 'windows-portability' not in release_ci or 'windows-latest' not in release_ci or "'3.14'" not in release_ci:
    errors.append('release-gate workflow missing Windows/Python 3.14 portability job')
benchmark_source=(ROOT/'tools/benchmark_p7.py').read_text(encoding='utf-8')
if 'PeakWorkingSetSize' not in benchmark_source or 'try:\n    import resource as _resource' not in benchmark_source:
    errors.append('benchmark_p7.py missing portable POSIX/Windows peak-RSS implementation')

# Manifest integrity. Manifest excludes itself and known transient Python/test artifacts.
def _manifest_eligible(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if path.name == 'MANIFEST.json':
        return False
    transient_dirs = {'.git', '.pytest_cache', '__pycache__', '.mypy_cache', '.ruff_cache', '.venv', 'venv', 'env', 'htmlcov', '.idea', '.vscode'}
    if any(part in transient_dirs or part.endswith('.egg-info') for part in rel.parts):
        return False
    if path.suffix in {'.pyc', '.pyo'} or path.name == '.coverage':
        return False
    return path.is_file()

man=j('MANIFEST.json')
if man:
    release_manifest_schema=j('spec/schemas/RELEASE_MANIFEST.schema.json')
    if release_manifest_schema:
        try: jsonschema.validate(man, release_manifest_schema)
        except Exception as e: errors.append(f"schema MANIFEST.json vs RELEASE_MANIFEST: {e.message if hasattr(e,'message') else e}")
    if engine_version and man.get('runtime_build_version') != engine_version:
        errors.append(f"manifest runtime_build_version mismatch: {man.get('runtime_build_version')} vs {engine_version}")
    tracked={x['path']:x for x in man['files']}
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if _manifest_eligible(p)}
    if set(tracked)!=actual:
        errors.append(f"manifest file set mismatch missing={sorted(actual-set(tracked))} extra={sorted(set(tracked)-actual)}")
    for rel,e in tracked.items():
        p=ROOT/rel
        if p.exists():
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h!=e['sha256']: errors.append(f"manifest hash mismatch: {rel}")
if errors:
    print('SPEC AUDIT FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('SPEC AUDIT OK')
print(f"release_gate_axes={len(release_axes)} phase_records=9 v0.1_use_cases={len([u for u in uc['use_cases'] if u['implementation_target']=='v0.1'])}")
