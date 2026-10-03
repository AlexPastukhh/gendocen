import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_tool(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class P8ManifestToolTests(unittest.TestCase):
    def test_manifest_ignores_git_metadata_but_tracks_repository_control_files(self):
        tool=load_tool('release_manifest')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'.git/objects').mkdir(parents=True)
            (root/'.git/HEAD').write_text('ref: refs/heads/main\n')
            (root/'.git/objects/probe').write_bytes(b'git-internal')
            (root/'.pytest_cache').mkdir()
            (root/'.pytest_cache/probe').write_text('transient')
            (root/'.gitignore').write_bytes(b'__pycache__/\n')
            (root/'.gitattributes').write_bytes(b'* text=auto eol=lf\n')
            (root/'.github/workflows').mkdir(parents=True)
            (root/'.github/workflows/ci.yml').write_bytes(b'name: CI\n')
            (root/'tracked.txt').write_text('tracked')
            paths={e['path'] for e in tool.generate(root,'test','0.1.0.dev18','P8','accepted')['files']}
            self.assertNotIn('.git/HEAD',paths)
            self.assertNotIn('.git/objects/probe',paths)
            self.assertNotIn('.pytest_cache/probe',paths)
            self.assertIn('.gitignore',paths)
            self.assertIn('.gitattributes',paths)
            self.assertIn('.github/workflows/ci.yml',paths)
            self.assertIn('tracked.txt',paths)

    def test_manifest_refuses_git_normalized_text_with_crlf(self):
        tool=load_tool('release_manifest')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'.gitattributes').write_bytes(b'* text=auto eol=lf\n')
            (root/'evidence.txt').write_bytes(b'line one\r\nline two\r\n')
            with self.assertRaises(ValueError):
                tool.generate(root,'test','0.1.0.dev20','P8','accepted')
            # Validation also exposes the class explicitly if a stale manifest exists.
            payload={
                'manifest_schema_version':'1.0.0',
                'package':'generic-documentation-engine-spec-runtime',
                'version':'test',
                'target_engine_version':'0.1.0',
                'runtime_build_version':'0.1.0.dev20',
                'implementation_phase':'P8',
                'implementation_status':'accepted',
                'files':tool.entries(root),
            }
            (root/'MANIFEST.json').write_text(json.dumps(payload), encoding='utf-8')
            result=tool.validate(root,root/'MANIFEST.json')
            self.assertFalse(result['ok'])
            self.assertIn('manifest_noncanonical_text_eol',{x['code'] for x in result['findings']})

    def test_manifest_detects_tamper_and_missing_file(self):
        tool=load_tool('release_manifest')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'a.txt').write_text('a'); (root/'b.txt').write_text('b')
            from docengine.versions import ENGINE_VERSION
            payload=tool.generate(root,'test',ENGINE_VERSION,'P8','acceptance_review')
            (root/'MANIFEST.json').write_text(json.dumps(payload))
            self.assertTrue(tool.validate(root,root/'MANIFEST.json')['ok'])
            (root/'a.txt').write_text('changed')
            result=tool.validate(root,root/'MANIFEST.json')
            self.assertFalse(result['ok']); self.assertIn('manifest_content_mismatch',{x['code'] for x in result['findings']})
            (root/'b.txt').unlink()
            result=tool.validate(root,root/'MANIFEST.json')
            self.assertIn('manifest_missing_file',{x['code'] for x in result['findings']})

class P8AxisAuditTests(unittest.TestCase):
    def test_axis_audit_rejects_pending_and_accepts_complete_closure(self):
        tool=load_tool('audit_axes')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'spec/registries').mkdir(parents=True)
            (root/'plan/phase_records').mkdir(parents=True)
            shutil.copy2(ROOT/'spec/registries/ACCEPTANCE_AXES.json',root/'spec/registries/ACCEPTANCE_AXES.json')
            for src in (ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json'):
                shutil.copy2(src,root/'plan/phase_records'/src.name)
            p8_path=root/'plan/phase_records/P8_EXECUTION_RECORD.json'
            p8=json.loads(p8_path.read_text(encoding="utf-8"))
            p8['status']='acceptance_review'
            p8_path.write_text(json.dumps(p8))
            result=tool.audit(root,check_evidence_refs=False)
            self.assertFalse(result['ok'])
            self.assertIn('p8_not_accepted',{x['code'] for x in result['findings']})

            p8['status']='accepted'
            for criterion in p8['acceptance_criteria']:
                criterion['status']='pass'
                if not criterion.get('evidence_refs'): criterion['evidence_refs']=['test-evidence']
            for axis in p8['axis_reviews']:
                axis['status']='pass'
                if not axis.get('evidence_refs'): axis['evidence_refs']=['test-evidence']
            p8_path.write_text(json.dumps(p8))
            result=tool.audit(root,check_evidence_refs=False)
            self.assertTrue(result['ok'],result['findings'])
            self.assertIn('DAX18',result['promoted_release_axes'])



    def test_axis_audit_requires_explicit_carried_gate_for_partial_accepted_phase(self):
        tool=load_tool('audit_axes')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'spec/registries').mkdir(parents=True)
            (root/'plan/phase_records').mkdir(parents=True)
            shutil.copy2(ROOT/'spec/registries/ACCEPTANCE_AXES.json',root/'spec/registries/ACCEPTANCE_AXES.json')
            for src in (ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json'):
                shutil.copy2(src,root/'plan/phase_records'/src.name)
            p7_path=root/'plan/phase_records/P7_EXECUTION_RECORD.json'
            p7=json.loads(p7_path.read_text(encoding="utf-8"))
            p7.pop('carried_release_gates',None)
            p7_path.write_text(json.dumps(p7))
            result=tool.audit(root,check_evidence_refs=False)
            self.assertFalse(result['ok'])
            codes={x['code'] for x in result['findings']}
            self.assertIn('accepted_phase_incomplete_criterion',codes)
            self.assertIn('accepted_phase_incomplete_axis',codes)

    def test_axis_audit_detects_missing_path_like_evidence_ref(self):
        tool=load_tool('audit_axes')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'spec/registries').mkdir(parents=True)
            (root/'plan/phase_records').mkdir(parents=True)
            shutil.copy2(ROOT/'spec/registries/ACCEPTANCE_AXES.json',root/'spec/registries/ACCEPTANCE_AXES.json')
            for src in (ROOT/'plan/phase_records').glob('P*_EXECUTION_RECORD.json'):
                shutil.copy2(src,root/'plan/phase_records'/src.name)
            # Make every current path-like ref resolvable by disabling the broad check
            # once, then inject one missing ref and copy only its parent owner record.
            p8_path=root/'plan/phase_records/P8_EXECUTION_RECORD.json'
            p8=json.loads(p8_path.read_text(encoding="utf-8"))
            p8['acceptance_criteria'][0]['evidence_refs']=['plan/evidence/does-not-exist.json']
            p8_path.write_text(json.dumps(p8))
            result=tool.audit(root,check_evidence_refs=True)
            self.assertFalse(result['ok'])
            self.assertTrue(any(x['code']=='evidence_ref_missing' and x['ref']=='plan/evidence/does-not-exist.json' for x in result['findings']))


class P8BenchmarkReproducibilityTests(unittest.TestCase):
    def test_release_benchmark_runs_from_clean_source_without_external_pythonpath(self):
        with tempfile.TemporaryDirectory() as td:
            budget=Path(td)/'budget.json'
            budget.write_text(json.dumps({
                'budget_schema_version':'1.0.0',
                'benchmark_schema_version':'2.0.0',
                'fixture':{'targets':10,'edges':50,'structured_diffs':10,'markdown_renders':10},
                'normalization':{'kind':'pure_python_integer_mix_v1','iterations':1000,'samples':1,'statistic':'median','description':'test'},
                'limits':{
                    'normalized_total_ratio_max':1000.0,'max_rss_kib':1000000,
                    'edge_count_must_equal':50,'changed_diffs_must_equal':1,'targets_must_equal':10,
                    'structured_diffs_must_equal':10,'markdown_renders_must_equal':10,'query_hits_must_equal':50,
                },
                'policy':{'blocking':True,'rationale':'test','established_before_release_rerun':True,'p7_reference':'plan/evidence/P7/benchmark_10k_50k.json'},
            }))
            env=os.environ.copy(); env.pop('PYTHONPATH',None)
            proc=subprocess.run([sys.executable,str(ROOT/'tools/benchmark_release.py'),'--budget',str(budget),'--json'],cwd=ROOT,env=env,capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            payload=json.loads(proc.stdout)
            self.assertTrue(payload['ok'])
            self.assertNotIn('benchmark_execution_failed',{x.get('code') for x in payload.get('errors',[])})

class P8ReleaseLifecycleTests(unittest.TestCase):
    def test_bundled_fixture_release_lifecycle(self):
        tool=load_tool('release_check'); result=tool.check(ROOT)
        self.assertTrue(result['ok'],result['findings'])

class P8SyntheticDomainFixtureTests(unittest.TestCase):
    def test_telemetry_numeric_fixture_build_dependency_verify_without_core_change(self):
        with tempfile.TemporaryDirectory() as td:
            project=Path(td)/'telemetry'; (project/'docs/_structured/telemetry').mkdir(parents=True); (project/'docengine_project').mkdir()
            (project/'docengine.toml').write_text('[docengine]\nconfig_version = 1\ndocumentation_root = "docs"\nstructured_dir = "_structured"\ndependency_dir = "_dependency"\nproject_package = "docengine_project"\n\n[schemas]\n')
            (project/'docs/_structured/telemetry/sensor.json').write_text(json.dumps({'$docengine':{'resource_id':'telemetry.sensor','materialize':[]},'data':{'reading':73,'scale':2}}))
            (project/'docs/_structured/telemetry/normalized.json').write_text(json.dumps({'$docengine':{'resource_id':'telemetry.normalized','resource_kind':'derived_descriptor','materialize':[]},'data':{}}))
            (project/'docengine_project/__init__.py').write_text('from .builders import register\n\ndef register_builders(registry):\n    register(registry)\n')
            (project/'docengine_project/builders.py').write_text('def build(ctx):\n    reading=ctx.read("resource://telemetry/sensor#/reading")\n    scale=ctx.read("resource://telemetry/sensor#/scale")\n    return {"normalized": reading/scale}\n\ndef register(registry):\n    registry.register("resource://telemetry/normalized", build, builder_id="telemetry.normalize", dependency_type="compute", comparator="exact")\n')
            env={'PYTHONPATH':str(ROOT/'src')}
            proc=subprocess.run([sys.executable,'-m','docengine.cli','rebuild','resource://telemetry/normalized','--project-root',str(project),'--json'],cwd=ROOT,env={**__import__('os').environ,**env},capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            payload=json.loads(proc.stdout); self.assertTrue(payload['ok']); self.assertEqual(payload['data']['status'],'valid')
            from docengine.project import discover_roots
            from docengine.resources import ResourceCatalog
            from docengine.extensions import load_project_extension
            from docengine.builders import BuildEngine
            roots=discover_roots(project_root=project); catalog=ResourceCatalog.scan(roots); extension=load_project_extension(roots,catalog)
            built=BuildEngine(catalog,extension.registry).build('resource://telemetry/normalized')
            self.assertEqual(built.data['normalized'],36.5)
            verify=subprocess.run([sys.executable,'-m','docengine.cli','verify','--project-root',str(project),'--json'],cwd=ROOT,env={**__import__('os').environ,**env},capture_output=True,text=True)
            self.assertEqual(verify.returncode,0,verify.stdout+verify.stderr); self.assertTrue(json.loads(verify.stdout)['ok'])
