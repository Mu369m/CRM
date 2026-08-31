from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from .master import BrokerTenant

_legacy_module_path = Path(__file__).resolve().parents[1] / "models.py"
_spec = spec_from_file_location("app._legacy_models", _legacy_module_path)
if _spec is not None and _spec.loader is not None:
    _legacy_module = module_from_spec(_spec)
    _spec.loader.exec_module(_legacy_module)
    for _name in dir(_legacy_module):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_legacy_module, _name)

__all__ = sorted({name for name in globals() if not name.startswith("_")})
