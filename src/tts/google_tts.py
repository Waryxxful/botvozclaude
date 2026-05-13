import hashlib
import structlog
from google.cloud import texttospeech_v1 as tts

from config.settings import get_settings
from .base import BaseTTS

logger = structlog.get_logger(__name__)

# Caché simple en memoria para frases frecuentes (saludo, despedida, etc.)
_cache: dict[str, bytes] = {}
_CACHE_MAX_SIZE = 50


class GoogleTTS(BaseTTS):
    """Google Text-to-Speech con voces neurales en español."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = tts.TextToSpeechAsyncClient()
        self._default_voice = settings.bot_tts_voice
        self._default_language = settings.bot_default_language

    async def synthesize(
        self,
        text: str,
        language: str | None = None,
        voice: str | None = None,
        speed: float = 1.0,
        pitch: float = 0.0,
    ) -> bytes:
        lang = language or self._default_language
        voice_name = voice or self._default_voice

        cache_key = hashlib.md5(f"{voice_name}:{lang}:{speed}:{pitch}:{text}".encode()).hexdigest()
        if cache_key in _cache:
            logger.debug("tts_cache_hit", text_length=len(text))
            return _cache[cache_key]

        synthesis_input = tts.SynthesisInput(text=text)
        voice_params = tts.VoiceSelectionParams(
            language_code=lang,
            name=voice_name,
        )
        audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=speed,
            pitch=pitch,
        )

        try:
            response = await self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            audio_bytes = response.audio_content

            if len(_cache) < _CACHE_MAX_SIZE:
                _cache[cache_key] = audio_bytes

            logger.debug("tts_synthesized", text_length=len(text), audio_bytes=len(audio_bytes))
            return audio_bytes

        except Exception as exc:
            logger.error("google_tts_error", error=str(exc), text_preview=text[:50])
            raise

    async def close(self) -> None:
        await self._client.transport.close()
