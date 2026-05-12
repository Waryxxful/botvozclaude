import asyncio
import structlog
from typing import AsyncIterator

from google.cloud.speech_v2 import SpeechAsyncClient
from google.cloud.speech_v2.types import (
    RecognitionConfig,
    StreamingRecognitionConfig,
    StreamingRecognizeRequest,
    SpeechAdaptation,
)

from config.settings import get_settings
from .base import BaseSTT

logger = structlog.get_logger(__name__)


class GoogleSTT(BaseSTT):
    """Google Speech-to-Text v2 con streaming en español."""

    def __init__(self) -> None:
        settings = get_settings()
        self._project_id = settings.gcp_project_id
        self._client = SpeechAsyncClient()

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        language: str = "es-419",
    ) -> AsyncIterator[tuple[str, bool]]:
        recognizer = f"projects/{self._project_id}/locations/global/recognizers/_"

        recognition_config = RecognitionConfig(
            explicit_decoding_config=RecognitionConfig.ExplicitDecodingConfig(
                encoding=RecognitionConfig.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1,
            ),
            language_codes=[language],
            model="latest_long",
            features=RecognitionConfig.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=False,
            ),
        )

        streaming_config = StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=StreamingRecognitionConfig.StreamingRecognitionFeatures(
                enable_voice_activity_events=True,
                interim_results=True,
            ),
        )

        async def request_generator():
            # Primer mensaje: configuración
            yield StreamingRecognizeRequest(
                recognizer=recognizer,
                streaming_config=streaming_config,
            )
            # Mensajes siguientes: audio
            async for chunk in audio_chunks:
                yield StreamingRecognizeRequest(audio=chunk)

        try:
            async for response in await self._client.streaming_recognize(
                requests=request_generator()
            ):
                for result in response.results:
                    if result.alternatives:
                        text = result.alternatives[0].transcript
                        is_final = result.is_final
                        if text.strip():
                            yield text.strip(), is_final
        except Exception as exc:
            logger.error("google_stt_error", error=str(exc))
            raise

    async def close(self) -> None:
        await self._client.transport.close()
