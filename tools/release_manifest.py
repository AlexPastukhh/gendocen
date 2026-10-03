#!/usr/bin/env python3
"""Generate or validate the deterministic engine release manifest."""
from __future__ import annotations
import argparse, hashlib, json, pathlib

DEFAULT_ROOT=pathlib.Path(__file__).resolve().parents[1]
TRANSIENT={'.git','.pytest_cache','__pycache__','build','.mypy_cache','.ruff_cache','.venv','venv','env','htmlcov','.idea','.vscode'}

def eligible(root:pathlib.Path,path:pathlib.Path)->bool:
    rel=path.relative_to(root)
    if path.name=='MANIFEST.json': return False
    if any(part in TRANSIENT or part.endswith('.egg-info') for part in rel.parts): return False
    if path.suffix in {'.pyc','.pyo'} or path.name=='.coverage': return False
    return path.is_file()

BINARY_SUFFIXES={'.whl','.zip','.png','.jpg','.jpeg','.gif','.pdf'}

def _utf8_text_with_noncanonical_eol(path:pathlib.Path,data:bytes)->bool:
    if path.suffix.lower() in BINARY_SUFFIXES or b'\x00' in data:
        return False
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return b'\r' in data

def noncanonical_text_eols(root:pathlib.Path)->list[str]:
    findings=[]
    for p in sorted(root.rglob('*'),key=lambda x:x.relative_to(root).as_posix()):
        if eligible(root,p):
            data=p.read_bytes()
            if _utf8_text_with_noncanonical_eol(p,data):
                findings.append(p.relative_to(root).as_posix())
    return findings

def entries(root:pathlib.Path):
    out=[]
    for p in sorted(root.rglob('*'),key=lambda x:x.relative_to(root).as_posix()):
        if eligible(root,p):
            data=p.read_bytes(); out.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
    return out

def generate(root:pathlib.Path,version:str,runtime:str,phase:str,status:str)->dict:
    bad_eols=noncanonical_text_eols(root)
    if bad_eols:
        raise ValueError('non-canonical CR/CRLF in Git-normalized UTF-8 text: '+', '.join(bad_eols))
    return {'manifest_schema_version':'1.0.0','package':'generic-documentation-engine-spec-runtime','version':version,'target_engine_version':'0.1.0','runtime_build_version':runtime,'implementation_phase':phase,'implementation_status':status,'files':entries(root)}

def validate(root:pathlib.Path,path:pathlib.Path)->dict:
    try: m=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: return {'ok':False,'tracked_files':0,'actual_files':len(entries(root)),'findings':[{'code':'manifest_unreadable','message':str(exc)}]}
    findings=[]
    required={'manifest_schema_version','package','version','target_engine_version','runtime_build_version','implementation_phase','implementation_status','files'}
    if set(m)!=required: findings.append({'code':'manifest_shape_invalid','actual_keys':sorted(m)})
    if m.get('manifest_schema_version')!='1.0.0': findings.append({'code':'manifest_schema_unsupported','actual':m.get('manifest_schema_version')})
    tracked={e.get('path'):e for e in m.get('files',[]) if isinstance(e,dict) and isinstance(e.get('path'),str)}
    for rel in noncanonical_text_eols(root): findings.append({'code':'manifest_noncanonical_text_eol','path':rel})
    actual={e['path']:e for e in entries(root)}
    for rel in sorted(set(actual)-set(tracked)): findings.append({'code':'manifest_untracked_file','path':rel})
    for rel in sorted(set(tracked)-set(actual)): findings.append({'code':'manifest_missing_file','path':rel})
    for rel in sorted(set(tracked)&set(actual)):
        if tracked[rel].get('sha256')!=actual[rel]['sha256'] or tracked[rel].get('size')!=actual[rel]['size']:
            findings.append({'code':'manifest_content_mismatch','path':rel})
    return {'ok':not findings,'tracked_files':len(tracked),'actual_files':len(actual),'findings':findings}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=pathlib.Path,default=DEFAULT_ROOT); sub=ap.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate'); g.add_argument('--version',required=True); g.add_argument('--runtime',required=True); g.add_argument('--phase',default='P8'); g.add_argument('--status',default='acceptance_review'); g.add_argument('--output',type=pathlib.Path)
    v=sub.add_parser('validate'); v.add_argument('--manifest',type=pathlib.Path); v.add_argument('--json',action='store_true')
    a=ap.parse_args(); root=a.root.resolve()
    if a.command=='generate':
        output=a.output or root/'MANIFEST.json'
        try:
            payload=generate(root,a.version,a.runtime,a.phase,a.status)
        except ValueError as exc:
            print(f"manifest generation refused: {exc}")
            return 1
        output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"wrote {output} files={len(payload['files'])}")
        return 0
    path=a.manifest or root/'MANIFEST.json'; result=validate(root,path); print(json.dumps(result,sort_keys=True) if a.json else json.dumps(result,indent=2,sort_keys=True)); return 0 if result['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
