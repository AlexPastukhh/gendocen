"""Registration index for mirrored deterministic builders.

Project target logic lives under ``builders/<logical-target>.py``. This flat index is
retained because accepted regression tests exercise project-code replacement through it.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_mirrored(relative: str):
    path = Path(__file__).with_name("builders") / relative
    spec = spec_from_file_location(f"product_tax_builder_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load mirrored builder: {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register(registry):
    _load_mirrored("catalog/price_with_tax.py").register(registry)
