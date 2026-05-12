import structlog
from typing import AsyncIterator

from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

from config.settings import get_settings
from .base import BaseSTT

logger = structlog.get_logger(__name__)


class DeepgramSTT(BaseSTT):
    """Deepgram Nova-2 — fallback de baja latencia."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = DeepgramClient(settings.deepgram_api_key)

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        language: str = "es-419",
    ) -> AsyncIterator[tuple[str, bool]]:
        # Deepgram usa "es" o "es-419"
        dg_language = language if language.startswith("es") else "es"

        options = LiveOptions(
            model="nova-2",
            language=dg_language,
            punctuate=True,
            interim_results=True,
            encoding="linear16",
            sample_rate=16000,
            channels=1,
        )

        results: list[tuple[str, bool]] = []
        done_event = __import__("asyncio").Event()

        connection = self._client.listen.asyncwebsocket.v("1")

        async def on_message(self_conn, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript
            is_final = result.is_final
            if sentence.strip():
                results.append((sentence.strip(), is_final))

        async def on_close(self_conn, close, **kwargs):
            done_event.set()

        connection.on(LiveTranscriptionEvents.Transcript, on_message)
        connection.on(LiveTranscriptionEvents.Close, on_close)

        await connection.start(options)

        async for chunk in audio_chunks:
            await connection.send(chunk)

        await connection.finish()
        await done_event.wait()

        for item in results:
            yield item

    async def close(self) -> None:
        pass
