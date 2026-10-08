#!/usr/bin/env python3
"""Whole-check source-I/O regression; timing is reported, never a platform SLA."""
import argparse, collections, contextlib, io, json, pathlib, statistics, sys, tempfile, time
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from docengine.builders import BuildOperation
from docengine.cli import main as cli
from docengine.versions import ENGINE_VERSION


def measure(size, repeat):
    records = []
    for _ in range(repeat):
        with tempfile.TemporaryDirectory(prefix='docengine-snapshot-bench-') as temporary:
            project = pathlib.Path(temporary)
            (project/'docs').mkdir(); (project/'docengine_project').mkdir()
            (project/'docengine.toml').write_text('[docengine]\nconfig_version=1\ndocumentation_root="docs"\nproject_package="docengine_project"\n')
            (project/'docengine_project/__init__.py').write_text(
                'def register_builders(registry): pass\ndef register_semantic_dependencies(registry):\n'
                f'    for i in range({size}): registry.register("file://consumer-"+str(i)+".md", ["file://owner-"+str(i)+".md"])\n')
            for i in range(size):
                (project/'docs'/f'consumer-{i}.md').write_text('# Consumer\nUses its selected canonical source.\n')
                (project/'docs'/f'owner-{i}.md').write_text('# Owner\n'+('Canonical documentation content. '*70)+'\n')
            sources = set((project/'docs').glob('*.md'))
            reads = collections.Counter(); validations = []
            original_read = pathlib.Path.read_bytes
            original_validate = BuildOperation.assert_current
            def read(path):
                if path in sources: reads[path] += 1
                return original_read(path)
            def validate(operation):
                validations.append(operation)
                return original_validate(operation)
            output = io.StringIO(); start = time.perf_counter()
            with patch.object(pathlib.Path,'read_bytes',read), patch.object(BuildOperation,'assert_current',validate), contextlib.redirect_stdout(output):
                code = cli(['check','--project-root',str(project),'--json'])
            seconds = time.perf_counter()-start
            payload = json.loads(output.getvalue())
            ok = code == 2 and payload['data']['counts'] == {'review_required':size} and len(validations)==1 and len(reads)==2*size and set(reads.values())=={2}
            records.append(dict(seconds=round(seconds,6),source_byte_reads=sum(reads.values()),sources=len(reads),full_validations=len(validations),exit=code,ok=ok))
    return dict(targets=size,median_seconds=round(statistics.median(r['seconds'] for r in records),6),records=records,ok=all(r['ok'] for r in records))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--json',action='store_true')
    args = parser.parse_args()
    if args.repeat < 1: parser.error('--repeat must be positive')
    samples = [measure(size,args.repeat) for size in (16,64,128)]
    result = dict(runtime=ENGINE_VERSION,python=sys.version,platform=sys.platform,workload='Independent initially unvalidated plain-Markdown semantic pairs',contract='One capture plus one final byte validation per unique source; one full command validation',samples=samples,ok=all(s['ok'] for s in samples))
    print(json.dumps(result,sort_keys=True,indent=None if args.json else 2))
    return 0 if result['ok'] else 1


if __name__=='__main__': raise SystemExit(main())
