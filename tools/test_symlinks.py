#!/usr/bin/env python3
"""Prepare and run the current pytest requires_symlink profile with retained reports."""
from __future__ import annotations
import argparse, contextlib, ctypes, datetime, hashlib, json, os, pathlib, subprocess, sys, tempfile, uuid
import xml.etree.ElementTree as ET
from release_manifest import entries

ROOT = pathlib.Path(__file__).resolve().parents[1]


def write_json(path, value):
    # Overwrite the pre-created file in place: retain the preparing user's ACL.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def elevated():
    return bool(ctypes.windll.shell32.IsUserAnAdmin()) if sys.platform == 'win32' else None


def pytest_run(output, temporary, collect=False):
    import pytest
    class Selection:
        nodeids = []
        def pytest_collection_finish(self, session):
            self.nodeids = [item.nodeid for item in session.items]
    selected = Selection()
    args = ['tests', '-m', 'requires_symlink', '-q', '-p', 'no:cacheprovider', '--tb=short', '--strict-markers', '--basetemp='+str(temporary/'p')]
    args += ['--collect-only'] if collect else ['--junitxml='+str(output/'junit.xml')]
    prefix = 'collect' if collect else 'pytest'
    with (output/(prefix+'.stdout.txt')).open('w', encoding='utf-8') as out, (output/(prefix+'.stderr.txt')).open('w', encoding='utf-8') as err:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = int(pytest.main(args, plugins=[selected]))
    return code, selected.nodeids


def capability(output):
    probe = output/'capability'
    probe.mkdir()
    target = probe/'file'; target.write_bytes(b'probe')
    directory = probe/'directory'; directory.mkdir()
    (probe/'file-link').symlink_to(target)
    (probe/'directory-link').symlink_to(directory, target_is_directory=True)


def counts_from_xml(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    counts = {key:sum(int(s.get(key, '0')) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    counts['passed'] = counts['tests']-counts['failures']-counts['errors']-counts['skipped']
    return counts


def quote_powershell(text):
    return "'"+str(text).replace("'", "''")+"'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true', help='Collect marked tests and create readable report files; run without elevation')
    mode.add_argument('--run', type=pathlib.Path, metavar='PREPARED_DIRECTORY', help='Run tests using a directory created by --prepare')
    parser.add_argument('--output-root', type=pathlib.Path, help='For --prepare only; report storage must be outside the checkout')
    parser.add_argument('--temp-root', type=pathlib.Path, help='For --prepare only; short writable parent for test fixtures (default: system temporary directory)')
    args = parser.parse_args()
    if args.run and (args.output_root or args.temp_root):
        parser.error('--output-root and --temp-root are only valid with --prepare')
    if args.prepare:
        base = (args.output_root or pathlib.Path(tempfile.gettempdir())/'docengine-symlink-tests').resolve()
        if base.is_relative_to(ROOT):
            parser.error('Report storage must be outside the repository')
        base.mkdir(parents=True, exist_ok=True)
        output = base/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12])
        # Path.mkdir inherits the parent's ACL; do not use Windows mkdtemp(mode=0700).
        output.mkdir()
        for name in ('result.json', 'prepared.json', 'selected.json', 'collect.stdout.txt', 'collect.stderr.txt', 'pytest.stdout.txt', 'pytest.stderr.txt', 'junit.xml'):
            (output/name).write_bytes(b'')
    else:
        output = args.run.resolve()
        if output.is_relative_to(ROOT) or not output.is_dir():
            parser.error('--run requires a prepared directory outside the checkout')
        if not (output/'prepared.json').is_file():
            parser.error('Missing prepared.json; use --prepare first')
        if (output/'execution-started.txt').exists():
            parser.error('This directory already executed; use --prepare for a new run')
    report = dict(report_schema_version='1.0.0', repository=str(ROOT), python=sys.executable, platform=sys.platform,
                  elevated=elevated(), collection_only=args.prepare, output_directory=str(output), complete=False, ok=False)
    print('Reports: '+str(output), flush=True)
    try:
        if args.prepare:
            temporary_parent = (args.temp_root or pathlib.Path(tempfile.gettempdir())).resolve()
            if temporary_parent.is_relative_to(ROOT):
                raise RuntimeError('Test temporary storage must be outside the repository')
            temporary_parent.mkdir(parents=True, exist_ok=True)
            temporary = temporary_parent/('gd'+uuid.uuid4().hex[:8])
            temporary.mkdir()
        else:
            prepared = json.loads((output/'prepared.json').read_text(encoding='utf-8'))
            if not prepared.get('temporary_directory'):
                raise RuntimeError('Preparation predates separate temporary storage; use --prepare again')
            temporary = pathlib.Path(prepared['temporary_directory']).resolve()
            if temporary.is_relative_to(ROOT) or not temporary.is_dir():
                raise RuntimeError('Prepared temporary directory is missing or inside the checkout; prepare again')
        report['temporary_directory'] = str(temporary)
        os.environ.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        tempfile.tempdir = str(temporary)
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(ROOT/'src'), str(ROOT)]
        os.chdir(ROOT)
        before = entries(ROOT)
        if args.prepare:
            code, nodes = pytest_run(output, temporary, collect=True)
            write_json(output/'selected.json', nodes)
            unchanged = entries(ROOT) == before
            report.update(pytest_exit=code, selected_count=len(nodes), repository_unchanged=unchanged, complete=True, ok=code==0 and bool(nodes) and unchanged)
            if report['ok']:
                write_json(output/'prepared.json', dict(repository=str(ROOT), python=sys.executable, files=before, selected=nodes, temporary_directory=str(temporary)))
        else:
            if pathlib.Path(prepared['repository']).resolve() != ROOT or pathlib.Path(prepared['python']).resolve() != pathlib.Path(sys.executable).resolve():
                raise RuntimeError('Prepared repository/interpreter differs; prepare again with this interpreter')
            if before != prepared['files']:
                raise RuntimeError('Repository changed since preparation; run --prepare again')
            try:
                with (output/'execution-started.txt').open('x', encoding='utf-8') as started:
                    started.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
            except FileExistsError:
                print('Another process already started this run; use --prepare again', file=sys.stderr)
                return 1
            capability(output)
            report['symlinks_available'] = True
            code, nodes = pytest_run(output, temporary)
            write_json(output/'selected.json', nodes)
            counts = counts_from_xml(output/'junit.xml')
            unchanged = entries(ROOT) == before
            report.update(pytest_exit=code, selected_count=len(nodes), counts=counts, repository_unchanged=unchanged, complete=True,
                          ok=code==0 and bool(nodes) and nodes==prepared['selected'] and counts['tests']==len(nodes) and counts['passed']==len(nodes) and unchanged)
        write_json(output/'result.json', report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        if args.prepare and report['ok']:
            if sys.platform == 'win32':
                # Print commands for the user; never request elevation automatically.
                argument = subprocess.list2cmdline(['-u', str(pathlib.Path(__file__).resolve()), '--run', str(output)])
                print('Run in ordinary PowerShell, approve UAC, then read the result:', flush=True)
                print('Start-Process -FilePath '+quote_powershell(sys.executable)+' -ArgumentList '+quote_powershell(argument)+' -Verb RunAs -Wait', flush=True)
                print('Get-Content -Raw '+quote_powershell(output/'result.json'), flush=True)
            else:
                print('Run: '+subprocess.list2cmdline([sys.executable, str(pathlib.Path(__file__).resolve()), '--run', str(output)]), flush=True)
        return 0 if report['ok'] else 1
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc), winerror=getattr(exc, 'winerror', None))
        write_json(output/'result.json', report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return 4 if getattr(exc, 'winerror', None)==1314 else 1


if __name__ == '__main__':
    raise SystemExit(main())
