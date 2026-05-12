import assemblyai as aai
from django.conf import settings


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe a local audio file via AssemblyAI.

    Returns {"id": str, "text": str} where text uses 'Speaker A/B' labels.
    """
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

    config = aai.TranscriptionConfig(
        speech_models=["universal-3-pro", "universal-2"],
        language_code="es",
        speaker_labels=True,
    )

    transcript = aai.Transcriber().transcribe(audio_path, config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    if transcript.utterances:
        lines = [f"Speaker {u.speaker}: {u.text}" for u in transcript.utterances]
        text = "\n".join(lines)
    else:
        text = transcript.text or ""

    return {"id": transcript.id, "text": text}
