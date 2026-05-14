"""Shim — re-implements bot_config using BOT_VOZ YAML profiles and local schema shim."""

from pathlib import Path
import yaml
from .bot_profiles.schema import BotProfileSchema

# Point to BOT_VOZ's actual YAML profiles directory
_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "bot_profiles"


def load_bot_profile(profile_name: str = "default") -> BotProfileSchema:
    profile_path = _PROFILES_DIR / f"{profile_name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Perfil de bot no encontrado: {profile_path}")
    with open(profile_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BotProfileSchema.model_validate(data)


_default_profile: BotProfileSchema | None = None


def get_default_profile() -> BotProfileSchema:
    global _default_profile
    if _default_profile is None:
        _default_profile = load_bot_profile("default")
    return _default_profile
