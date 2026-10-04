"""Project-owned extension surface for the sample documentation project.

Flat registration indexes remain for historical/regression compatibility; target logic
itself lives in mirrored builders/ and dependency_rules/ trees.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_index(filename: str):
    path = Path(__file__).with_name(filename)
    spec = spec_from_file_location(f"{__name__}._index_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load project registration index: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register_builders(registry):
    _load_index("builders.py").register(registry)


def register_semantic_dependencies(registry):
    _load_index("semantic_rules.py").register(registry)
