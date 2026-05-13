import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock

from config.bot_profiles.schema import BotProfileSchema, GuardrailConfig, MemoryConfig, ToolsConfig
from src.session.session_state import SessionState


# ── Stubs globales para módulos GCP/audio opcionales ─────────────────────────
def _ensure_stub(name: str, **attrs):
    """Crea un módulo stub si no existe, con los atributos dados."""
    if name not in sys.modules:
        m = types.ModuleType(name)
        sys.modules[name] = m
    for k, v in attrs.items():
        setattr(sys.modules[name], k, v)
    return sys.modules[name]


# google namespace
_ensure_stub("google")
_ensure_stub("google.cloud")

# google.cloud.storage necesita Client para que patch() funcione
_ensure_stub("google.cloud.storage", Client=MagicMock())
setattr(sys.modules["google.cloud"], "storage", sys.modules["google.cloud.storage"])

# Otros servicios GCP
for _ns in (
    "google.cloud.pubsub_v1", "google.cloud.firestore",
    "google.cloud.firestore_v1", "google.cloud.firestore_v1.async_client",
    "google.cloud.speech", "google.cloud.speech_v2", "google.cloud.speech_v2.types",
    "google.cloud.texttospeech", "google.cloud.texttospeech_v1",
    "vertexai", "vertexai.generative_models",
):
    _ensure_stub(_ns)

# Dependencias de audio/telefonía opcionales
for _ns in ("webrtcvad", "deepgram", "soundfile", "telnyx"):
    _ensure_stub(_ns)


@pytest.fixture
def sample_profile() -> BotProfileSchema:
    return BotProfileSchema(
        name="test",
        description="Perfil de prueba",
        system_prompt="Eres un asistente de prueba.",
        greeting="Hola, ¿en qué te ayudo?",
        farewell="Hasta luego.",
        guardrails=GuardrailConfig(forbidden_topics=["política"]),
        memory=MemoryConfig(max_history_turns=5),
        tools=ToolsConfig(enabled=["save_customer_data"]),
    )


@pytest.fixture
def sample_session(sample_profile) -> SessionState:
    return SessionState(
        call_id="test-call-001",
        caller_number="+5491112345678",
        bot_profile=sample_profile,
    )
