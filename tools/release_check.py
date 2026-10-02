#!/usr/bin/env python3
"""P8 source-checkout lifecycle release check over bundled fixtures."""
from __future__ import annotations
import argparse, json, os, pathlib, shutil, subprocess, sys, tempfile

DEFAULT_ROOT=pathlib.Path(__file__).resolve().parents[1]

def run(root:pathlib.Path, project:pathlib.Path, args:list[str])->dict:
    env=os.environ.copy(); env['PYTHONPATH']=str(root/'src')
    cmd=[sys.executable,'-m','docengine.cli',*args,'--project-root',str(project),'--json']
    proc=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True)
    try: payload=json.loads(proc.stdout)
    except Exception: payload={'raw_stdout':proc.stdout,'raw_stderr':proc.stderr}
    return {'args':args,'exit_code':proc.returncode,'payload':payload,'stderr':proc.stderr}

def check(root:pathlib.Path)->dict:
    steps=[]; findings=[]
    with tempfile.TemporaryDirectory(prefix='docengine-p8-release-') as td:
        td=pathlib.Path(td)
        product=td/'product'; sample=td/'sample'
        shutil.copytree(root/'examples/product_tax_project',product)
        shutil.copytree(root/'examples/sample_project',sample)
        # Product fixture must already verify clean.
        step=run(root,product,['verify']); steps.append({'name':'product_verify_initial',**step})
        if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'product_initial_verify_failed'})
        # Delete every currently generated Markdown view and prove clean recreation.
        for path in (product/'docs/catalog').glob('*.md'): path.unlink()
        step=run(root,product,['materialize','--all']); steps.append({'name':'product_clean_materialize',**step})
        if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'product_clean_materialize_failed'})
        step=run(root,product,['verify']); steps.append({'name':'product_verify_regenerated',**step})
        if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'product_regenerated_verify_failed'})
        # Fresh sample lifecycle: no hidden runtime evidence from archive may be required.
        shutil.rmtree(sample/'docs/_dependency',ignore_errors=True)
        step=run(root,sample,['sync','--all']); steps.append({'name':'sample_sync_initial',**step})
        if step['exit_code']!=2 or not step['payload'].get('attention_required'): findings.append({'code':'sample_initial_attention_contract_failed'})
        target='file://architecture/rationale.md'
        step=run(root,sample,['explain',target]); steps.append({'name':'sample_explain',**step})
        context=step['payload'].get('data',{}).get('review_context_id')
        if step['exit_code']!=2 or not context: findings.append({'code':'sample_review_packet_failed'})
        if context:
            step=run(root,sample,['validate',target,'--result','still-valid','--reason','P8 release lifecycle review','--review-context',context,'--actor-kind','ci']); steps.append({'name':'sample_validate',**step})
            if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'sample_validation_failed'})
        step=run(root,sample,['sync']); steps.append({'name':'sample_sync_final',**step})
        if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'sample_final_sync_failed'})
        step=run(root,sample,['verify']); steps.append({'name':'sample_verify_final',**step})
        if step['exit_code']!=0 or not step['payload'].get('ok'): findings.append({'code':'sample_final_verify_failed'})
    return {'ok':not findings,'findings':findings,'steps':steps}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=pathlib.Path,default=DEFAULT_ROOT); ap.add_argument('--json',action='store_true'); a=ap.parse_args(); result=check(a.root.resolve()); print(json.dumps(result,sort_keys=True) if a.json else json.dumps(result,indent=2,sort_keys=True)); return 0 if result['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
