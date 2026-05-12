import structlog
from datetime import datetime

from config.bot_config import load_bot_profile, get_default_profile
from src.persistence.firestore_client import get_firestore_client
from src.persistence.models import CallRecord, CallStatus, CustomerData
from .session_state import SessionState

logger = structlog.get_logger(__name__)

# Sesiones activas en memoria: call_id → SessionState
_sessions: dict[str, SessionState] = {}


def create_session(call_id: str, caller_number: str, profile_name: str = "default") -> SessionState:
    """Crea una nueva sesión de llamada."""
    try:
        profile = load_bot_profile(profile_name)
    except FileNotFoundError:
        logger.warning("profile_not_found_using_default", profile=profile_name)
        profile = get_default_profile()

    session = SessionState(
        call_id=call_id,
        caller_number=caller_number,
        bot_profile=profile,
    )
    _sessions[call_id] = session
    logger.info("session_created", call_id=call_id, caller=caller_number, profile=profile.name)
    return session


def get_session(call_id: str) -> SessionState | None:
    return _sessions.get(call_id)


def get_all_sessions() -> dict[str, SessionState]:
    return dict(_sessions)


async def close_session(call_id: str) -> None:
    """Cierra la sesión y persiste la transcripción en Firestore."""
    session = _sessions.pop(call_id, None)
    if session is None:
        logger.warning("session_not_found_on_close", call_id=call_id)
        return

    end_time = datetime.utcnow()
    duration = (end_time - session.start_time).total_seconds()

    record = CallRecord(
        call_id=call_id,
        caller_number=session.caller_number,
        bot_profile=session.bot_profile.name,
        status=CallStatus.TRANSFERRED if session.transferred_to else CallStatus.COMPLETED,
        start_time=session.start_time,
        end_time=end_time,
        duration_seconds=duration,
        transcription=[msg.to_transcription_entry() for msg in session.conversation_history],
        customer_data=CustomerData(**session.customer_data) if session.customer_data else None,
        transferred_to=session.transferred_to,
        metadata=session.metadata,
    )

    try:
        firestore = get_firestore_client()
        await firestore.save_call(record)
        if record.customer_data:
            await firestore.save_customer(call_id, record.customer_data)
        logger.info("session_closed_and_saved", call_id=call_id, duration_s=round(duration, 1))
    except Exception as exc:
        logger.error("session_save_failed", call_id=call_id, error=str(exc))
