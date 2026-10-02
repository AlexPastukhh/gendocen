#!/usr/bin/env python3
"""P8 environment-normalized performance release gate."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, statistics, subprocess, sys, time

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_BUDGET=ROOT/'spec/release/PERFORMANCE_BUDGET.json'


def calibration(iterations: int) -> float:
    start=time.perf_counter(); x=0x12345678
    mask=(1<<64)-1
    for i in range(iterations):
        x ^= (x << 13) & mask; x ^= x >> 7; x ^= (x << 17) & mask; x=(x+i)&mask
    elapsed=time.perf_counter()-start
    if x == -1: print('unreachable')
    return elapsed


def load_budget(path: pathlib.Path) -> dict:
    d=json.loads(path.read_text(encoding='utf-8'))
    if d.get('budget_schema_version')!='1.0.0': raise SystemExit('unsupported performance budget schema')
    return d


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--budget',type=pathlib.Path,default=DEFAULT_BUDGET)
    ap.add_argument('--json',action='store_true')
    args=ap.parse_args(); budget=load_budget(args.budget)
    norm=budget['normalization']; fixture=budget['fixture']; limits=budget['limits']
    samples=[calibration(int(norm['iterations'])) for _ in range(int(norm['samples']))]
    cal_median=statistics.median(samples)
    cmd=[sys.executable,str(ROOT/'tools/benchmark_p7.py'),'--targets',str(fixture['targets']),'--edges',str(fixture['edges']),'--json']
    env=os.environ.copy()
    src_path=str(ROOT/'src')
    existing=env.get('PYTHONPATH')
    env['PYTHONPATH']=src_path if not existing else src_path+os.pathsep+existing
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,env=env)
    if proc.returncode!=0:
        result={'benchmark_schema_version':'2.0.0','ok':False,'errors':[{'code':'benchmark_execution_failed','message':proc.stderr.strip() or f'exit {proc.returncode}'}]}
        print(json.dumps(result,sort_keys=True)); return 1
    raw=json.loads(proc.stdout)
    ratio=float(raw['seconds']['total'])/cal_median if cal_median>0 else float('inf')
    checks={
        'normalized_total_ratio': {'actual':ratio,'limit':float(limits['normalized_total_ratio_max']),'ok':ratio<=float(limits['normalized_total_ratio_max'])},
        'max_rss_kib': {'actual':int(raw['environment']['max_rss_kib']),'limit':int(limits['max_rss_kib']),'ok':int(raw['environment']['max_rss_kib'])<=int(limits['max_rss_kib'])},
        'edge_count': {'actual':int(raw['edge_count_reported']),'limit':int(limits['edge_count_must_equal']),'ok':int(raw['edge_count_reported'])==int(limits['edge_count_must_equal'])},
        'changed_diffs': {'actual':int(raw['operations']['changed_diffs']),'limit':int(limits['changed_diffs_must_equal']),'ok':int(raw['operations']['changed_diffs'])==int(limits['changed_diffs_must_equal'])},
        'targets': {'actual':int(raw['targets']),'limit':int(limits['targets_must_equal']),'ok':int(raw['targets'])==int(limits['targets_must_equal'])},
        'structured_diffs': {'actual':int(raw['operations']['structured_diffs']),'limit':int(limits['structured_diffs_must_equal']),'ok':int(raw['operations']['structured_diffs'])==int(limits['structured_diffs_must_equal'])},
        'markdown_renders': {'actual':int(raw['operations']['markdown_renders']),'limit':int(limits['markdown_renders_must_equal']),'ok':int(raw['operations']['markdown_renders'])==int(limits['markdown_renders_must_equal'])},
        'query_hits': {'actual':int(raw['query_hits']),'limit':int(limits['query_hits_must_equal']),'ok':int(raw['query_hits'])==int(limits['query_hits_must_equal'])},
    }
    ok=all(x['ok'] for x in checks.values())
    result={
        'benchmark_schema_version':'2.0.0','ok':ok,'budget':budget,'budget_sha256':hashlib.sha256(args.budget.read_bytes()).hexdigest(),
        'calibration':{'samples_seconds':samples,'median_seconds':cal_median},
        'benchmark':raw,'checks':checks,
    }
    print(json.dumps(result,sort_keys=True) if args.json else json.dumps(result,indent=2,sort_keys=True))
    return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
