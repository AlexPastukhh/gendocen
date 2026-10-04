"""Unrelated-domain fixture proving the builder core is generic.

The fixture retains a flat ``builders.py`` registration index for accepted regression
compatibility while the actual target implementation lives in mirrored builders/ code.
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
