from pathlib import Path
import yaml
from .bot_profiles.schema import BotProfileSchema

_PROFILES_DIR = Path(__file__).parent / "bot_profiles"


def load_bot_profile(profile_name: str = "default") -> BotProfileSchema:
    """Carga y valida un perfil de bot desde archivo YAML."""
    profile_path = _PROFILES_DIR / f"{profile_name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Perfil de bot no encontrado: {profile_path}")

    with open(profile_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return BotProfileSchema.model_validate(data)


# Perfil por defecto (singleton para evitar re-lectura en cada request)
_default_profile: BotProfileSchema | None = None


def get_default_profile() -> BotProfileSchema:
    global _default_profile
    if _default_profile is None:
        _default_profile = load_bot_profile("default")
    return _default_profile
