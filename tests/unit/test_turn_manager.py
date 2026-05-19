import pytest
from src.session.session_state import TurnState
from src.session.turn_manager import TurnManager


def test_speech_start_changes_to_listening(sample_session):
    tm = TurnManager(sample_session)
    barge_in = tm.on_speech_start()
    assert not barge_in
    assert sample_session.turn_state == TurnState.LISTENING


def test_speech_end_changes_to_processing(sample_session):
    tm = TurnManager(sample_session)
    tm.on_speech_start()
    ready = tm.on_speech_end()
    assert ready
    assert sample_session.turn_state == TurnState.PROCESSING


async def test_barge_in_when_speaking(sample_session):
    import asyncio
    tm = TurnManager(sample_session)
    dummy_task = asyncio.ensure_future(asyncio.sleep(0))
    tm.on_speaking_start(dummy_task)
    assert sample_session.turn_state == TurnState.SPEAKING

    barge_in = tm.on_speech_start()
    assert barge_in
    assert sample_session.turn_state == TurnState.LISTENING


async def test_speaking_end_returns_to_idle(sample_session):
    import asyncio
    tm = TurnManager(sample_session)
    dummy_task = asyncio.ensure_future(asyncio.sleep(0))
    tm.on_speaking_start(dummy_task)
    tm.on_speaking_end()
    assert sample_session.turn_state == TurnState.IDLE
