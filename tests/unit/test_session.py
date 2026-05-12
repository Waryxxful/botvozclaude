import pytest
from src.persistence.models import TranscriptionRole
from src.session.session_state import SessionState, TurnState


def test_add_message_populates_history(sample_session):
    sample_session.add_message(TranscriptionRole.USER, "Hola")
    sample_session.add_message(TranscriptionRole.ASSISTANT, "¡Hola! ¿En qué te ayudo?")
    assert len(sample_session.conversation_history) == 2


def test_history_trim_on_max_turns(sample_session):
    # max_history_turns=5 → máximo 10 mensajes (5 user + 5 assistant)
    for i in range(12):
        role = TranscriptionRole.USER if i % 2 == 0 else TranscriptionRole.ASSISTANT
        sample_session.add_message(role, f"Mensaje {i}")
    assert len(sample_session.conversation_history) == 10


def test_get_history_for_llm_format(sample_session):
    sample_session.add_message(TranscriptionRole.USER, "Hola")
    history = sample_session.get_history_for_llm()
    assert history[0]["role"] == "user"
    assert history[0]["parts"][0]["text"] == "Hola"


def test_turn_state_initial_idle(sample_session):
    assert sample_session.turn_state == TurnState.IDLE
