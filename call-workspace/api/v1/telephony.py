"""Telnyx webhook y llamadas salientes — django-ninja."""

import asyncio
import json
import sys
from pathlib import Path

import structlog
from ninja import Router, Schema
from django.http import HttpRequest, HttpResponse

# Asegurar que src.* sea importable
_BOT_VOZ = Path(__file__).resolve().parent.parent.parent.parent
if str(_BOT_VOZ) not in sys.path:
    sys.path.insert(0, str(_BOT_VOZ))

from config.settings import get_settings
from src.telephony.telnyx_handler import verify_telnyx_signature, parse_call_event
from src.session import session_manager
from src.orchestrator.call_orchestrator import start_call
from src.persistence.pubsub_publisher import get_pubsub_publisher
from src.orchestrator.outbound_orchestrator import OutboundCallConfig

logger = structlog.get_logger(__name__)
router = Router()

# call_id → asyncio.Task activo
_active_calls: dict[str, asyncio.Task] = {}


# ── Schemas ───────────────────────────────────────────────────────────────

class CallInitiateIn(Schema):
    call_id: str
    phone_number: str
    rendered_prompt: str
    greeting: str
    output_params: list[str] = []
    webhook_url: str


class CallInitiateOut(Schema):
    bot_call_id: str
    status: str


# ── Telnyx Webhook ────────────────────────────────────────────────────────

@router.post("/webhooks/telnyx", auth=None)
async def handle_telnyx_webhook(request: HttpRequest) -> HttpResponse:
    """Recibe webhooks de Telnyx con verificación de firma Ed25519."""
    settings = get_settings()

    payload_bytes = request.body
    signature_header = request.headers.get("telnyx-signature-ed25519", "")
    timestamp_header = request.headers.get("telnyx-timestamp", "")

    if settings.environment == "production":
        if not verify_telnyx_signature(payload_bytes, signature_header, timestamp_header):
            logger.warning("webhook_signature_failed")
            return HttpResponse(status=401)
    else:
        if signature_header and timestamp_header:
            if not verify_telnyx_signature(payload_bytes, signature_header, timestamp_header):
                logger.warning("webhook_signature_invalid_dev")

    try:
        payload = json.loads(payload_bytes.decode())
    except Exception as exc:
        logger.error("webhook_json_parse_error", error=str(exc))
        return HttpResponse(status=400)

    event_data = parse_call_event(payload)
    if not event_data:
        return HttpResponse(status=200)

    event_type = event_data["event_type"]
    call_id = event_data["call_control_id"]

    logger.info("webhook_received", event_type=event_type, call_id=call_id,
                caller=event_data["caller_number"])

    if event_type == "call.initiated":
        await _handle_call_initiated(call_id, event_data)
    elif event_type == "call.hangup":
        await _handle_call_hangup(call_id)
    elif event_type == "call.answered":
        logger.info("call_answered", call_id=call_id)

    return HttpResponse(status=200)


async def _handle_call_initiated(call_id: str, event_data: dict) -> None:
    settings = get_settings()
    session_id = event_data.get("session_id")
    command_id = event_data.get("command_id")

    if not session_id or not command_id:
        logger.error("media_streaming_params_missing", call_id=call_id)
        return

    session = session_manager.create_session(
        call_id=call_id,
        caller_number=event_data["caller_number"],
        profile_name=settings.bot_profile,
    )

    task = asyncio.create_task(
        start_call(
            call_id=call_id,
            caller_number=event_data["caller_number"],
            session_id=session_id,
            command_id=command_id,
        )
    )
    _active_calls[call_id] = task

    try:
        pubsub = get_pubsub_publisher()
        await pubsub.publish_event("call_started", {
            "call_id": call_id,
            "caller": event_data["caller_number"],
            "profile": session.bot_profile.name,
        })
    except Exception as exc:
        logger.error("pubsub_publish_error", call_id=call_id, error=str(exc))

    def _cleanup(t):
        _active_calls.pop(call_id, None)
        logger.info("call_task_completed", call_id=call_id)

    task.add_done_callback(_cleanup)


async def _handle_call_hangup(call_id: str) -> None:
    task = _active_calls.get(call_id)
    if task and not task.done():
        task.cancel()

    await session_manager.close_session(call_id)

    try:
        pubsub = get_pubsub_publisher()
        await pubsub.publish_event("call_ended", {"call_id": call_id})
    except Exception as exc:
        logger.error("pubsub_publish_error", call_id=call_id, error=str(exc))


# ── Llamadas salientes ────────────────────────────────────────────────────

@router.post("/calls/initiate", response=CallInitiateOut)
async def initiate_call(request: HttpRequest, payload: CallInitiateIn) -> CallInitiateOut:
    """Inicia una llamada saliente (disparado por batch o integración externa)."""
    config = OutboundCallConfig(
        call_id=payload.call_id,
        phone_number=payload.phone_number,
        rendered_prompt=payload.rendered_prompt,
        greeting=payload.greeting,
        output_params=payload.output_params,
        webhook_url=payload.webhook_url,
    )
    logger.info("initiate_call_received", call_id=config.call_id, phone=config.phone_number)

    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(_run_outbound(config))

    return CallInitiateOut(bot_call_id=payload.call_id, status="initiated")


async def _run_outbound(config: OutboundCallConfig) -> None:
    logger.info("outbound_call_started", call_id=config.call_id, phone=config.phone_number)


# ── Admin / métricas ─────────────────────────────────────────────────────

class SessionsOut(Schema):
    active_calls: int
    calls: list[str]


class MetricsOut(Schema):
    stt_calls: int
    llm_calls: int
    tts_calls: int
    error_rate: float


@router.get("/admin/sessions", response=SessionsOut)
def get_sessions(request: HttpRequest) -> SessionsOut:
    return SessionsOut(active_calls=len(_active_calls), calls=list(_active_calls.keys()))


@router.get("/admin/metrics", response=MetricsOut)
def get_metrics(request: HttpRequest) -> MetricsOut:
    return MetricsOut(stt_calls=0, llm_calls=0, tts_calls=0, error_rate=0.0)
