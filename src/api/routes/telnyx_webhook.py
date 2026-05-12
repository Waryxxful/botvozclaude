"""Webhook de Telnyx para recibir eventos de llamadas."""
import asyncio
import structlog
from fastapi import APIRouter, Request, Response

from config.settings import get_settings
from src.telephony.telnyx_handler import verify_telnyx_signature, parse_call_event
from src.session import session_manager
from src.orchestrator.call_orchestrator import start_call
from src.persistence.pubsub_publisher import get_pubsub_publisher

logger = structlog.get_logger(__name__)
router = APIRouter()

# Mapeo de call_id → asyncio.Task de CallOrchestrator
_active_calls: dict[str, asyncio.Task] = {}


@router.post("/webhooks/telnyx")
async def handle_telnyx_webhook(request: Request) -> Response:
    """Recibe webhooks de Telnyx con verificación de firma Ed25519."""
    settings = get_settings()

    # Leer payload
    payload_bytes = await request.body()
    signature_header = request.headers.get("telnyx-signature-ed25519", "")
    timestamp_header = request.headers.get("telnyx-timestamp", "")

    # Verificar firma Ed25519 (siempre en producción, opcional en desarrollo)
    if settings.environment == "production":
        if not verify_telnyx_signature(payload_bytes, signature_header, timestamp_header):
            logger.warning("webhook_signature_failed")
            return Response(status_code=401)
    else:
        # En desarrollo, permite webhooks sin firma válida para testing
        if signature_header and timestamp_header:
            if not verify_telnyx_signature(payload_bytes, signature_header, timestamp_header):
                logger.warning("webhook_signature_invalid_dev", hint="set ENVIRONMENT=production to enforce")

    # Parsear evento
    try:
        import json
        payload = json.loads(payload_bytes.decode())
    except Exception as exc:
        logger.error("webhook_json_parse_error", error=str(exc))
        return Response(status_code=400)

    event_data = parse_call_event(payload)
    if not event_data:
        logger.debug("webhook_no_call_event")
        return Response(status_code=200)

    event_type = event_data["event_type"]
    call_id = event_data["call_control_id"]

    logger.info(
        "webhook_received",
        event_type=event_type,
        call_id=call_id,
        caller=event_data["caller_number"],
    )

    # Procesar eventos
    if event_type == "call.initiated":
        await _handle_call_initiated(call_id, event_data)

    elif event_type == "call.hangup":
        await _handle_call_hangup(call_id)

    elif event_type == "call.answered":
        logger.info("call_answered", call_id=call_id)

    # Retornar 200 OK inmediatamente (el orquestador corre en background)
    return Response(status_code=200)


async def _handle_call_initiated(call_id: str, event_data: dict) -> None:
    """Inicia una llamada: crea sesión y CallOrchestrator con Telnyx Media Streaming."""
    settings = get_settings()

    # Extraer parámetros de Telnyx Media Streaming
    session_id = event_data.get("session_id")
    command_id = event_data.get("command_id")

    if not session_id or not command_id:
        logger.error(
            "media_streaming_params_missing",
            call_id=call_id,
            session_id=session_id,
            command_id=command_id,
        )
        return

    # Crear sesión
    session = session_manager.create_session(
        call_id=call_id,
        caller_number=event_data["caller_number"],
        profile_name=settings.bot_profile,
    )

    # Lanzar CallOrchestrator en background con Telnyx Media Streaming
    task = asyncio.create_task(
        start_call(
            call_id=call_id,
            caller_number=event_data["caller_number"],
            session_id=session_id,
            command_id=command_id,
        )
    )
    _active_calls[call_id] = task

    # Publicar evento en Pub/Sub
    try:
        pubsub = get_pubsub_publisher()
        await pubsub.publish_event("call_started", {
            "call_id": call_id,
            "caller": event_data["caller_number"],
            "profile": session.bot_profile.name,
        })
    except Exception as exc:
        logger.error("pubsub_publish_error", call_id=call_id, error=str(exc))

    # Limpiar cuando termine
    def _cleanup(t):
        _active_calls.pop(call_id, None)
        logger.info("call_task_completed", call_id=call_id)

    task.add_done_callback(_cleanup)


async def _handle_call_hangup(call_id: str) -> None:
    """Finaliza una llamada."""
    task = _active_calls.get(call_id)
    if task and not task.done():
        task.cancel()

    await session_manager.close_session(call_id)

    try:
        pubsub = get_pubsub_publisher()
        await pubsub.publish_event("call_ended", {"call_id": call_id})
    except Exception as exc:
        logger.error("pubsub_publish_error", call_id=call_id, error=str(exc))
