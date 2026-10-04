"""Historical P4 registration index; active rule semantics live in the mirrored tree.

Do not put sources, rule ids, dependency types, or comparators here.  This file exists
only so historical evidence/tests that name the flat registration path remain valid.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_mirrored(relative: str):
    path = Path(__file__).with_name("dependency_rules") / relative
    spec = spec_from_file_location(f"sample_rule_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load mirrored semantic rule: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register(registry):
    _load_mirrored("architecture/rationale.py").register(registry)
