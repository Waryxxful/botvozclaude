from datetime import datetime, timezone

from ninja import Router, Schema

from apps.calls.models import Call
from apps.calls.tasks import analyze_call

router = Router()


class TranscriptTurn(Schema):
    role: str
    text: str
    timestamp: float | None = None


class CallWebhookIn(Schema):
    call_id: str
    status: str
    duration_seconds: int
    audio_gcs_url: str
    transcript: list[TranscriptTurn]


@router.post("/webhook/", auth=None, response={200: dict, 404: dict})
def call_completed_webhook(request, payload: CallWebhookIn):
    try:
        call = Call.objects.get(pk=payload.call_id)
    except Call.DoesNotExist:
        return 404, {"detail": "call not found"}

    call.status = "analyzing"
    call.duration_seconds = payload.duration_seconds
    call.audio_gcs_url = payload.audio_gcs_url
    call.transcript = [turn.dict() for turn in payload.transcript]
    call.ended_at = datetime.now(timezone.utc)
    call.save(update_fields=["status", "duration_seconds", "audio_gcs_url", "transcript", "ended_at"])

    analyze_call.delay(str(call.id))
    return 200, {"received": True}
