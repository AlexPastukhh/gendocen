"""Registration index retained at the historical evidence path.

Active target logic lives under ``builders/<logical-target>.py``.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_mirrored(relative: str):
    path = Path(__file__).with_name("builders") / relative
    spec = spec_from_file_location(f"sample_builder_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load mirrored builder: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register(registry):
    _load_mirrored("architecture/system_summary.py").register(registry)
