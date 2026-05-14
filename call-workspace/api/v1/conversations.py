"""Endpoint para recibir grabaciones de conversaciones desde el browser."""
import json

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpRequest
from ninja import Router

router = Router()


@router.post("/conversations/upload", auth=None, response={200: dict, 400: dict})
def upload_recording(request: HttpRequest) -> tuple:
    """Recibe el audio WebM + transcript desde el bot de prueba."""
    session_id = request.POST.get("session_id", "").strip()
    if not session_id:
        return 400, {"detail": "session_id requerido"}

    audio_file: InMemoryUploadedFile | None = request.FILES.get("audio")
    transcript_raw = request.POST.get("transcript", "[]")
    script_name = request.POST.get("script_name", "")
    duration = request.POST.get("duration_seconds")

    try:
        transcript = json.loads(transcript_raw)
    except json.JSONDecodeError:
        transcript = []

    try:
        duration_f = float(duration) if duration else None
    except (TypeError, ValueError):
        duration_f = None

    from apps.conversations.models import ConversationRecording

    rec, created = ConversationRecording.objects.update_or_create(
        session_id=session_id,
        defaults={
            "script_name": script_name,
            "transcript": transcript,
            "duration_seconds": duration_f,
        },
    )

    if audio_file:
        audio_file.name = f"{session_id}.webm"
        rec.audio_file = audio_file
        rec.save(update_fields=["audio_file"])

    return 200, {
        "recording_id": rec.pk,
        "session_id": session_id,
        "has_audio": bool(rec.audio_file),
    }
