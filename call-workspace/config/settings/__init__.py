"""Django settings package. Exposes get_settings() for BOT_VOZ src.* compatibility."""

import importlib.util
from pathlib import Path

_cache = None


def get_settings():
    """Load and cache BOT_VOZ Pydantic settings. Required by src.tts, src.llm, etc."""
    global _cache
    if _cache is not None:
        return _cache
    # __file__ = call-workspace/config/settings/__init__.py
    # 4 parents up = BOT_VOZ/
    _settings_file = Path(__file__).resolve().parent.parent.parent.parent / "config" / "settings.py"
    _spec = importlib.util.spec_from_file_location("_botvoz_settings_impl", str(_settings_file))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _cache = _mod.get_settings()
    return _cache
