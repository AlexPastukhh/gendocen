"""Command snapshots: bounded source I/O, exact versions and final validation."""
import collections
import dataclasses
import hashlib
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest

from docengine.builders import BuildEngine, BuildOperation, BuilderRegistry, BuildSourceChangedError
from docengine.extensions import load_project_extension
from docengine.objects import RawObject
from docengine.project import discover_roots
from docengine.refs import ResourceRef
from docengine.resources import ResourceCatalog
from tests.test_documentation_workflows import run_json
from tests.test_builders import MemoryStore

ROOT = Path(__file__).resolve().parents[1]


def simple_project(tmp_path, size=1):
    project = tmp_path/'project'
    (project/'docs').mkdir(parents=True)
    (project/'docengine_project').mkdir()
    (project/'docengine.toml').write_text('[docengine]\nconfig_version=1\ndocumentation_root="docs"\nproject_package="docengine_project"\n')
    (project/'docengine_project/__init__.py').write_text(
        'def register_builders(registry): pass\n'
        'def register_semantic_dependencies(registry):\n'
        f'    for i in range({size}): registry.register("file://consumer-"+str(i)+".md", ["file://owner-"+str(i)+".md"])\n')
    for i in range(size):
        (project/'docs'/f'consumer-{i}.md').write_text('# Consumer\nUses its selected source.\n')
        (project/'docs'/f'owner-{i}.md').write_text('# Owner\n'+('Canonical content. '*120)+'\n')
    return project


def catalog(project):
    return ResourceCatalog.scan(discover_roots(project_root=project))


def counted_reads(paths):
    counts = collections.Counter()
    original = Path.read_bytes
    def read(path):
        if path in paths:
            counts[path] += 1
        return original(path)
    return counts, patch.object(Path, 'read_bytes', read)


@pytest.mark.parametrize('size', [16, 64, 128])
def test_full_check_reads_each_plain_source_once_then_validates_once(tmp_path, size):
    project = simple_project(tmp_path, size)
    paths = set((project/'docs').glob('*.md'))
    counts, reads = counted_reads(paths)
    validations = []
    original = BuildOperation.assert_current
    def validate(operation):
        validations.append(operation)
        return original(operation)
    with reads, patch.object(BuildOperation, 'assert_current', validate):
        code, report = run_json(['check','--project-root',str(project),'--json'])
    assert code == 2 and report['data']['counts'] == {'review_required':size}
    assert len(validations) == 1
    assert len(counts) == 2*size and set(counts.values()) == {2}


def test_plain_capture_preserves_bytes_version_and_normalized_text(tmp_path):
    project = simple_project(tmp_path)
    path = project/'docs/owner-0.md'
    content = 'первая\r\nвторая\rтретья\n'.encode('utf-8')
    path.write_bytes(content)
    operation = BuildOperation(catalog(project), BuilderRegistry(), validation='command')
    counts, reads = counted_reads({path})
    with reads:
        for _ in range(20):
            value, version = operation.source_value_and_version('file://owner-0.md')
            assert value == 'первая\nвторая\nтретья\n'
            assert version == hashlib.sha256(content).hexdigest()
        assert counts[path] == 1
        operation.assert_current()
        assert counts[path] == 2


def test_plain_edit_is_final_failure_and_stays_failed_after_restore(tmp_path):
    project = simple_project(tmp_path)
    source = project/'docs/owner-0.md'
    old = source.read_bytes()
    operation = BuildOperation(catalog(project), BuilderRegistry(), validation='command')
    first = operation.source_value_and_version('file://owner-0.md')
    source.write_text('changed\n')
    assert operation.source_value_and_version('file://owner-0.md') == first
    with pytest.raises(BuildSourceChangedError):
        operation.assert_current()
    source.write_bytes(old)
    with pytest.raises(BuildSourceChangedError):
        operation.source_value_and_version('file://owner-0.md')
    with pytest.raises(BuildSourceChangedError):
        operation.assert_current()
    fresh = BuildOperation(catalog(project), BuilderRegistry(), validation='command')
    assert fresh.source_value_and_version('file://owner-0.md') == first
    fresh.assert_current()


@pytest.mark.parametrize('change', ['delete','same_size_same_mtime','line_endings'])
def test_final_validation_uses_actual_bytes_not_timestamps(tmp_path, change):
    project = simple_project(tmp_path)
    source = project/'docs/owner-0.md'
    source.write_bytes(b'value=100\r\n')
    operation = BuildOperation(catalog(project), BuilderRegistry(), validation='command')
    operation.source_value_and_version('file://owner-0.md')
    stat = source.stat()
    if change == 'delete':
        source.unlink()
    elif change == 'line_endings':
        source.write_bytes(b'value=100\n')
    else:
        import os
        source.write_bytes(b'value=200\r\n')
        os.utime(source, ns=(stat.st_atime_ns,stat.st_mtime_ns))
    with pytest.raises(BuildSourceChangedError):
        operation.assert_current()


def test_raw_pointer_versions_share_snapshot_and_physical_validation(tmp_path):
    project = simple_project(tmp_path)
    source = project/'docs/_structured/raw/A.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'$docengine':{'resource_id':'raw.A','materialize':[]},'data':{'nested':{'x':0,'empty':None},'array':[False]}})+'\n')
    counts, reads = counted_reads({source})
    with reads:
        resources = catalog(project)
        operation = BuildOperation(resources, BuilderRegistry(), validation='command')
        refs = ['resource://raw/A','resource://raw/A#/nested/x','resource://raw/A#/nested/empty','resource://raw/A#/array/0']
        for _ in range(12):
            for ref in refs:
                value, version = operation.source_value_and_version(ref)
                assert version == resources.version(ref)
        assert counts[source] == 1, 'Managed scan captures source only once'
        operation.assert_current()
        assert counts[source] == 2
    source.write_text(source.read_text().replace('"x": 0','"x": 8'))
    assert operation.source_value_and_version(refs[1])[0] == 0
    with pytest.raises(BuildSourceChangedError):
        operation.assert_current()


def test_unobserved_change_and_restore_uses_same_pinned_value(tmp_path):
    project = simple_project(tmp_path)
    source = project/'docs/owner-0.md'
    old = source.read_bytes()
    operation = BuildOperation(catalog(project), BuilderRegistry(), validation='command')
    captured = operation.source_value_and_version('file://owner-0.md')
    source.write_text('temporary edit\n')
    assert operation.source_value_and_version('file://owner-0.md') == captured
    source.write_bytes(old)
    operation.assert_current()


def test_code_revision_is_validated_once_at_finalization(tmp_path):
    project = simple_project(tmp_path)
    resources = catalog(project)
    roots = discover_roots(project_root=project)
    extension = load_project_extension(roots, resources)
    operation = BuildOperation(resources, extension.registry, validation='command')
    source = project/'docengine_project/__init__.py'
    captured = operation.source_value_and_version('file://owner-0.md')
    source.write_text(source.read_text()+'\n# code changed\n')
    assert operation.source_value_and_version('file://owner-0.md') == captured
    with pytest.raises(BuildSourceChangedError,match='Python changed'):
        operation.assert_current()


def test_custom_store_retains_version_semantics_and_local_guards():
    store = MemoryStore({'raw.input':{'x':1}})
    operation = BuildOperation(store, BuilderRegistry(), validation='command')
    ref = 'resource://raw/input#/x'
    assert operation.source_value_and_version(ref) == (1,store.version(ref))
    old = store.objects['raw.input']
    store.objects['raw.input'] = RawObject.create(resource_id='raw.input',source_path=Path('/raw.json'),schema_uri=None,resource_kind='structured',data={'x':2})
    with pytest.raises(BuildSourceChangedError):
        operation.source_value_and_version(ref)
    store.objects['raw.input'] = old
    with pytest.raises(BuildSourceChangedError):
        operation.assert_current()


def test_metadata_owner_validation_is_deduplicated(tmp_path):
    project = tmp_path/'project'
    shutil.copytree(ROOT/'examples/field_dependency_project',project)
    resources = catalog(project)
    source = project/'docs/_structured/views/A.json'
    operation = BuildOperation(resources, BuilderRegistry(), validation='command')
    counts, reads = counted_reads({source})
    with reads:
        for _ in range(20): operation.observe_source('resource://views/A')
        assert counts[source] == 0
        operation.assert_current()
        assert counts[source] == 1
    source.write_text(source.read_text()+' ')
    with pytest.raises(BuildSourceChangedError): operation.assert_current()


@pytest.mark.parametrize('mutation', ['source','code'])
def test_warm_sync_rolls_back_prior_output_and_evidence_on_final_failure(tmp_path, mutation):
    project = tmp_path/'project'
    shutil.copytree(ROOT/'examples/field_dependency_project',project)
    assert run_json(['sync','--project-root',str(project),'--json'])[0] == 0
    watched = [project/'docs/views/A.md',project/'docs/views/B.md']
    runtime = project/'docs/_dependency'
    for name in ['receipts','baselines','state','materialization','events']:
        watched += [p for p in (runtime/name).rglob('*') if p.is_file()]
    original_bytes = {p:p.read_bytes() for p in watched}
    source = project/'docs/_structured/inputs/C.json'
    data = json.loads(source.read_text()); data['data']['x'] = 12
    source.write_text(json.dumps(data)+'\n')
    original = load_project_extension
    def load(*args, **kwargs):
        extension = original(*args, **kwargs)
        registry = BuilderRegistry(source_revision=extension.source_revision)
        registry.bind_revision_check(extension.registry._revision_check)
        done = []
        for spec in extension.registry.specs:
            def mutate(ctx, spec=spec):
                value = spec.function(ctx)
                if not done and str(spec.target)=='resource://fields/B_a1':
                    done.append(True)
                    if mutation == 'source':
                        data = json.loads(source.read_text()); data['data']['x'] = 500
                        source.write_text(json.dumps(data)+'\n')
                    else:
                        code = project/'docengine_project/fields.py'
                        code.write_text(code.read_text()+'\n# changed during operation\n')
                return value
            registry.register(spec.target,mutate,builder_id=spec.builder_id)
        return dataclasses.replace(extension,registry=registry)
    with patch('docengine.cli.load_project_extension',load):
        code, report = run_json(['sync','--project-root',str(project),'--json'])
    assert code == 3 and report['meta']['status']=='build_sources_changed', report
    assert all(p.read_bytes()==before for p,before in original_bytes.items())
    assert run_json(['sync','--project-root',str(project),'--json'])[0] == 0
    assert run_json(['verify','--project-root',str(project),'--json'])[0] == 0


def test_verify_reports_final_source_change_without_runtime_writes(tmp_path):
    project = simple_project(tmp_path)
    original = ResourceCatalog.capture_source
    source = project/'docs/owner-0.md'
    def mutate(resources,ref):
        value = original(resources,ref)
        if str(ref)=='file://owner-0.md': source.write_text('edited during verify\n')
        return value
    with patch.object(ResourceCatalog,'capture_source',mutate):
        code, report = run_json(['verify','--project-root',str(project),'--json'])
    assert code != 0
    assert any(f['code']=='build_sources_changed' for f in report['data']['report']['findings'])
    assert not (project/'docs/_dependency/state/dependency_state.json').exists()


@pytest.mark.parametrize('size', [16,64,128])
def test_wide_computed_graph_reads_shared_raw_source_only_at_scan_and_final(tmp_path, size):
    project = simple_project(tmp_path)
    source = project/'docs/_structured/raw/A.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'$docengine':{'resource_id':'raw.A','materialize':[]},'data':{'x':7}})+'\n')
    registry = BuilderRegistry()
    calls = collections.Counter()
    for i in range(size):
        def produce(ctx, i=i):
            calls[i] += 1
            return {'value':ctx.read('resource://raw/A#/x')+i}
        registry.register(f'resource://fields/f{i}',produce)
    registry.register('resource://views/A',lambda ctx:{'values':[ctx.read(f'resource://fields/f{i}#/value') for i in range(size)]})
    counts, reads = counted_reads({source})
    with reads:
        operation = BuildOperation(catalog(project),registry,validation='command')
        engine = BuildEngine(operation.store,registry,operation=operation)
        assert engine.build('resource://views/A').to_builtin()=={'values':list(range(7,7+size))}
        engine.build('resource://views/A')
        assert set(calls.values())=={1}
        assert counts[source]==1
        operation.assert_current()
        assert counts[source]==2
