import pytest
from unittest.mock import AsyncMock, MagicMock

from config.bot_profiles.schema import BotProfileSchema, GuardrailConfig, MemoryConfig, ToolsConfig
from src.session.session_state import SessionState


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
