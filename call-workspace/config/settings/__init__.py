"""Django settings package. Exposes get_settings() for BOT_VOZ src.* compatibility."""

import importlib.util
import os
from pathlib import Path

# BOT_VOZ root = 4 levels up from this file
_BOT_VOZ_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_cache = None


def get_settings():
    """Load and cache BOT_VOZ Pydantic settings. Required by src.tts, src.llm, etc."""
    global _cache
    if _cache is not None:
        return _cache

    # Load .env from BOT_VOZ root so GCP credentials are found
    from dotenv import load_dotenv
    load_dotenv(str(_BOT_VOZ_ROOT / ".env"), override=False)

    # Fix GOOGLE_APPLICATION_CREDENTIALS if it's a relative path
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds and not os.path.isabs(creds):
        abs_creds = str(_BOT_VOZ_ROOT / creds.lstrip("./"))
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = abs_creds

    _settings_file = _BOT_VOZ_ROOT / "config" / "settings.py"
    _spec = importlib.util.spec_from_file_location("_botvoz_settings_impl", str(_settings_file))
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _cache = _mod.get_settings()
    return _cache
