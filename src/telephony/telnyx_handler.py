"""Procesamiento de webhooks de Telnyx con validación Ed25519."""
import base64
import structlog
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from config.settings import get_settings

logger = structlog.get_logger(__name__)


def verify_telnyx_signature(payload: bytes, signature_header: str, timestamp_header: str) -> bool:
    """Verifica la firma Ed25519 de un webhook Telnyx.

    Telnyx firma los webhooks con Ed25519:
      - Public key: base64-encoded en TELNYX_PUBLIC_KEY
      - Mensaje firmado: timestamp + "|" + payload (bytes)
      - Firma: base64-encoded en el header telnyx-signature-ed25519
    """
    settings = get_settings()
    try:
        public_key_bytes = base64.b64decode(settings.telnyx_public_key)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

        signature_bytes = base64.b64decode(signature_header)
        message = f"{timestamp_header}|".encode() + payload

        public_key.verify(signature_bytes, message)
        return True
    except InvalidSignature:
        logger.warning("telnyx_signature_invalid")
        return False
    except Exception as exc:
        logger.error("telnyx_signature_error", error=str(exc))
        return False


def parse_call_event(payload: dict) -> dict | None:
    """Extrae los campos relevantes de un evento de llamada Telnyx."""
    data = payload.get("data", {})
    event_type = data.get("event_type", "")
    call_data = data.get("payload", {})

    if not event_type or not call_data:
        return None

    # Extraer información de Media Streaming (si está presente)
    media_streaming = call_data.get("media_streaming_options", {}) or {}

    return {
        "event_type": event_type,
        "call_control_id": call_data.get("call_control_id", ""),
        "call_leg_id": call_data.get("call_leg_id", ""),
        "caller_number": call_data.get("from", ""),
        "called_number": call_data.get("to", ""),
        "connection_id": call_data.get("connection_id", ""),
        "session_id": media_streaming.get("session_id", ""),
        "command_id": media_streaming.get("command_id", ""),
    }
