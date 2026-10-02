#!/usr/bin/env python3
"""P7 synthetic scalability baseline.

Default fixture: 10k targets / 50k dependency edges, plus 10k structured diffs and
10k deterministic Markdown renders. P7 records measurements; Q7.3 deliberately
defers the environment-normalized release budget to P8.
"""
from __future__ import annotations
import argparse, ctypes, json, os, platform, sys, time

try:
    import resource as _resource
except ImportError:  # Windows
    _resource = None
from docengine.dependencies import ComparatorRegistry, DependencyEntry, DependencyGraph, DependencyReceipt
from docengine.materialization import RenderContext, RendererRegistry
from docengine.refs import ResourceRef


def peak_rss_kib() -> int:
    """Return process peak RSS in KiB on POSIX and Windows."""
    if _resource is not None:
        value = int(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux and the other supported POSIX runners report KiB.
        return value // 1024 if sys.platform == "darwin" else value
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_ulong]
        get_process_memory_info.restype = ctypes.c_int
        if not get_process_memory_info(get_current_process(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.PeakWorkingSetSize // 1024)
    raise RuntimeError(f"unsupported platform for peak RSS measurement: {sys.platform}")


def build_receipts(targets: int, edges_per_target: int):
    baseline = "sha256:" + "0" * 64
    snap = "baseline://sha256/" + "0" * 64
    out=[]
    for i in range(targets):
        deps=[]
        for j in range(edges_per_target):
            source=f"resource://source/s{(i*edges_per_target+j)%targets}"
            deps.append(DependencyEntry(source,"resource","exact",baseline,snap,"sha256:"+"1"*64,"raw"))
        out.append(DependencyReceipt(
            receipt_id=f"receipt-{i:064x}", target=f"resource://target/t{i}", validated_at="2026-01-01T00:00:00Z",
            dependency_type="compute", dependencies=tuple(deps), builder_id="bench", builder_revision="sha256:"+"2"*64,
            output_digest="sha256:"+"3"*64,
        ))
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--targets',type=int,default=10000); ap.add_argument('--edges',type=int,default=50000); ap.add_argument('--json',action='store_true')
    a=ap.parse_args(); ept=max(1,a.edges//a.targets); edges=a.targets*ept

    t0=time.perf_counter(); receipts=build_receipts(a.targets,ept); t1=time.perf_counter()
    graph=DependencyGraph(receipts); t2=time.perf_counter(); payload=graph.to_dict(); t3=time.perf_counter()
    q0=time.perf_counter(); hits=0
    for i in range(0,a.targets,max(1,a.targets//100)):
        hits += len(graph.affected_by(f"resource://source/s{i}"))
    q1=time.perf_counter()

    comparator=ComparatorRegistry(); changed=0
    d0=time.perf_counter()
    for i in range(a.targets):
        old={'id':i,'name':f'item-{i}','values':[i,i+1,i+2]}
        new=old if i % 100 else {'id':i,'name':f'item-{i}-changed','values':[i,i+1,i+2]}
        changed += int(comparator.compare('json_structured',old,new).changed)
    d1=time.perf_counter()

    renderer=RendererRegistry().get('markdown')
    ctx=RenderContext(ResourceRef.parse('resource://bench/item'),'bench.item','managed','bench/item.md','markdown')
    rendered_bytes=0
    r0=time.perf_counter()
    for i in range(a.targets):
        text=renderer.function({'title':f'Item {i}','value':i,'tags':['a','b','c']},ctx)
        rendered_bytes += len(text.encode('utf-8') if isinstance(text,str) else text)
    r1=time.perf_counter()

    result={
        'benchmark_schema_version':'1.0.0','targets':a.targets,'edges':edges,'edges_per_target':ept,
        'operations':{'structured_diffs':a.targets,'changed_diffs':changed,'markdown_renders':a.targets,'rendered_bytes':rendered_bytes},
        'seconds':{
            'fixture':t1-t0,'graph_build':t2-t1,'graph_serialize':t3-t2,'reverse_queries':q1-q0,
            'structured_diff':d1-d0,'markdown_render':r1-r0,'total':r1-t0,
        },
        'edge_count_reported':payload['edge_count'],'query_hits':hits,
        'environment':{'python':platform.python_version(),'platform':platform.platform(),'max_rss_kib':peak_rss_kib()},
        'acceptance_budget_status':'baseline_only_p7_budget_deferred_to_p8'
    }
    print(json.dumps(result,sort_keys=True) if a.json else json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__': main()
