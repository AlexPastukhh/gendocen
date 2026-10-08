"""Keep direct filesystem-link security tests discoverable by the maintained profile."""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_direct_symlink_creators_are_marked_for_profile():
    missing = []
    creators = []
    for path in Path(__file__).parent.rglob('test_*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith('test_'):
                continue
            creates = any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in ('symlink', 'symlink_to') for call in ast.walk(node))
            if creates:
                creators.append(path.name+'::'+node.name)
                marked = any(ast.unparse(decorator).split('(',1)[0]=='pytest.mark.requires_symlink' for decorator in node.decorator_list)
                if not marked:
                    missing.append(path.name+'::'+node.name)
    assert creators, 'The security profile has no direct symlink tests'
    assert not missing, 'Add @pytest.mark.requires_symlink to: '+', '.join(missing)


def test_long_reports_keep_fixture_copy_and_journal_paths_usable(tmp_path):
    root = Path(__file__).resolve().parents[1]
    checkout = tmp_path/'checkout'
    (checkout/'tools').mkdir(parents=True)
    (checkout/'tests').mkdir()
    for name in ('test_symlinks.py', 'release_manifest.py'):
        shutil.copyfile(root/'tools'/name, checkout/'tools'/name)
    (checkout/'pyproject.toml').write_text('[tool.pytest.ini_options]\nmarkers = ["requires_symlink: link capability profile"]\n')
    (checkout/'tests/test_profile.py').write_text('import pytest\n@pytest.mark.requires_symlink\ndef test_profile(): pass\n')
    reports = tmp_path/'reports'/('r'*40)
    subprocess.run([sys.executable, '-B', str(checkout/'tools/test_symlinks.py'), '--prepare', '--output-root', str(reports)], check=True, capture_output=True)
    prepared_path = next(reports.glob('*/prepared.json'))
    prepared = json.loads(prepared_path.read_text())
    temporary = Path(prepared['temporary_directory'])
    try:
        assert not temporary.is_relative_to(reports)
        assert not temporary.is_relative_to(checkout)
        project = temporary/'p'/'test_lifecycle_symlinks_are_re0'/'project'
        shutil.copytree(root/'examples/product_tax_project', project)
        journal = project/'docs/_dependency/hardening/transaction_preparation/txn-00000000-0000-4000-8000-000000000079/journal.json.tmp-12-abcdef01'
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_bytes(b'fixture remains writable')
        assert journal.read_bytes() == b'fixture remains writable'
        assert list((project/'docs/_dependency/receipts').glob('receipt-*.json'))
    finally:
        shutil.rmtree(temporary)
