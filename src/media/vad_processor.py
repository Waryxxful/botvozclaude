"""Voice Activity Detection usando webrtcvad."""
import asyncio
import structlog

try:
    import webrtcvad
    _WEBRTCVAD_AVAILABLE = True
except ImportError:
    webrtcvad = None  # type: ignore[assignment]
    _WEBRTCVAD_AVAILABLE = False

from src.media.audio_utils import chunk_audio, STT_SAMPLE_RATE

logger = structlog.get_logger(__name__)

VAD_FRAME_MS = 20           # webrtcvad soporta 10, 20, 30ms
SILENCE_FRAMES_TO_END = 25  # 25 frames × 20ms = 500ms de silencio → fin de turno
SPEECH_FRAMES_TO_START = 3  # 3 frames con voz → inicio de turno


class VADProcessor:
    """Detecta inicio y fin de habla en un stream de audio PCM.

    Emite callbacks on_speech_start y on_speech_end con los chunks acumulados.
    """

    def __init__(
        self,
        aggressiveness: int = 2,
        sample_rate: int = STT_SAMPLE_RATE,
        on_speech_start=None,
        on_speech_end=None,
    ) -> None:
        if not _WEBRTCVAD_AVAILABLE:
            raise RuntimeError("webrtcvad no está instalado — VADProcessor no disponible")
        self._vad = webrtcvad.Vad(aggressiveness)
        self._sample_rate = sample_rate
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end

        self._speaking = False
        self._speech_frames: list[bytes] = []
        self._silence_count = 0
        self._voice_count = 0

    async def process_chunk(self, pcm_chunk: bytes) -> None:
        """Procesa un chunk de audio PCM y detecta eventos de voz."""
        frames = chunk_audio(pcm_chunk, VAD_FRAME_MS, self._sample_rate)

        for frame in frames:
            if len(frame) < (self._sample_rate * 2 * VAD_FRAME_MS) // 1000:
                continue  # Frame incompleto, descartar

            try:
                is_speech = self._vad.is_speech(frame, self._sample_rate)
            except Exception:
                continue

            if is_speech:
                self._silence_count = 0
                self._voice_count += 1

                if not self._speaking and self._voice_count >= SPEECH_FRAMES_TO_START:
                    self._speaking = True
                    self._speech_frames = []
                    logger.debug("vad_speech_start")
                    if self._on_speech_start:
                        await self._on_speech_start()

                if self._speaking:
                    self._speech_frames.append(frame)
            else:
                self._voice_count = 0
                if self._speaking:
                    self._silence_count += 1
                    self._speech_frames.append(frame)  # Incluir silencio final

                    if self._silence_count >= SILENCE_FRAMES_TO_END:
                        self._speaking = False
                        self._silence_count = 0
                        audio = b"".join(self._speech_frames)
                        self._speech_frames = []
                        logger.debug("vad_speech_end", audio_bytes=len(audio))
                        if self._on_speech_end:
                            await self._on_speech_end(audio)
