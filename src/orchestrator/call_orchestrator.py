"""Orquestador principal de una llamada. Un task asyncio por llamada activa."""
import asyncio
import structlog

from config.settings import get_settings
from src.session import session_manager
from src.session.turn_manager import TurnManager
from src.media.telnyx_media_client import TelnexMediaStreamingClient
from src.media.vad_processor import VADProcessor
from src.media.audio_utils import mulaw_to_pcm16, pcm16_to_mulaw
from src.persistence.pubsub_publisher import get_pubsub_publisher
from src.tts.google_tts import GoogleTTS
from .event_bus import EventBus, EventType
from .pipeline import run_stt, run_llm_and_tts

logger = structlog.get_logger(__name__)

_tts: GoogleTTS | None = None


def _get_tts() -> GoogleTTS:
    global _tts
    if _tts is None:
        _tts = GoogleTTS()
    return _tts


class CallOrchestrator:
    """Gestiona el ciclo completo de una llamada vía Telnyx Media Streaming."""

    def __init__(self, call_id: str, caller_number: str, session_id: str, command_id: str) -> None:
        self._call_id = call_id
        self._caller_number = caller_number
        self._session_id = session_id
        self._command_id = command_id
        self._bus = EventBus(call_id)
        self._telnyx_media: TelnexMediaStreamingClient | None = None
        self._session = None
        self._turn_manager: TurnManager | None = None
        self._active = True

    async def start(self) -> None:
        """Inicia la llamada: conecta Telnyx Media, saluda al cliente, entra al bucle."""
        pubsub = get_pubsub_publisher()
        settings = get_settings()

        # Crear sesión
        self._session = session_manager.create_session(
            self._call_id, self._caller_number, settings.bot_profile
        )
        self._turn_manager = TurnManager(self._session)

        # VAD para detectar fin de habla del usuario
        self._vad = VADProcessor(
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end,
        )

        # Wrapper síncrono para procesar audio de Telnyx (conversion + VAD)
        def process_telnyx_audio(audio_mulaw: bytes) -> None:
            """Convierte y procesa audio de Telnyx sin await."""
            pcm16 = mulaw_to_pcm16(audio_mulaw)
            self._vad.process_chunk(pcm16)

        # Conectar a Telnyx Media Streaming WebSocket
        self._telnyx_media = TelnexMediaStreamingClient(
            call_id=self._call_id,
            session_id=self._session_id,
            command_id=self._command_id,
            on_audio_chunk=process_telnyx_audio,
        )

        if not await self._telnyx_media.connect():
            logger.error("telnyx_media_connection_failed", call_id=self._call_id)
            await session_manager.close_session(self._call_id)
            return

        await pubsub.publish_call_event("call_started", self._call_id, caller=self._caller_number)

        # Saludo inicial
        await self._speak(self._session.bot_profile.greeting)

        # Bucle principal — espera eventos del bus
        await self._main_loop()

    async def _main_loop(self) -> None:
        while self._active:
            try:
                event = await asyncio.wait_for(self._bus.consume(), timeout=1.0)
                self._bus.task_done()

                if event.type == EventType.CALL_HANGUP:
                    await self._handle_hangup()
                    break

            except asyncio.TimeoutError:
                # Verificar tiempo máximo de llamada
                if self._session:
                    from datetime import datetime
                    elapsed = (datetime.utcnow() - self._session.start_time).total_seconds()
                    max_duration = self._session.bot_profile.guardrails.max_call_duration_seconds
                    if elapsed > max_duration:
                        logger.warning("call_max_duration_reached", call_id=self._call_id)
                        await self._speak(self._session.bot_profile.farewell)
                        await self._handle_hangup()
                        break

    async def _on_speech_start(self) -> None:
        barge_in = self._turn_manager.on_speech_start()
        if barge_in:
            await self._bus.publish(EventType.SPEECH_START, barge_in=True)

    async def _on_speech_end(self, audio_bytes: bytes) -> None:
        if not self._turn_manager.on_speech_end():
            return

        await self._bus.publish(EventType.SPEECH_END, audio_bytes_len=len(audio_bytes))
        self._turn_manager.on_processing_start()

        # Pipeline STT → LLM → TTS
        user_text = await run_stt(audio_bytes, self._session, self._bus)

        if not user_text:
            logger.warning("stt_no_result", call_id=self._call_id)
            self._turn_manager.on_speaking_end()
            return

        response_text = await run_llm_and_tts(
            user_text, self._session, self._bus, self._send_audio
        )

        # Verificar si hubo transferencia durante el procesamiento
        if self._session.transferred_to:
            await self._handle_hangup()

    async def _send_audio(self, audio_bytes: bytes) -> None:
        """Envía audio TTS al usuario vía Telnyx Media Streaming.

        Audio TTS llega en PCM16 24kHz. Se convierte a μ-law 8kHz para Telnyx.
        """
        if not self._telnyx_media:
            return

        # Convertir PCM16 24kHz → μ-law 8kHz para Telnyx
        audio_mulaw = pcm16_to_mulaw(audio_bytes)

        await self._telnyx_media.send_audio(audio_mulaw)

    async def _speak(self, text: str) -> None:
        """Sintetiza y envía audio (bloqueante para el saludo/despedida)."""
        if not text:
            return
        audio = await _get_tts().synthesize(text, language=self._session.bot_profile.language)
        tts_task = asyncio.ensure_future(self._send_audio(audio))
        self._turn_manager.on_speaking_start(tts_task)
        await tts_task
        self._turn_manager.on_speaking_end()

    async def _handle_hangup(self) -> None:
        """Cierra la llamada limpiamente."""
        self._active = False
        pubsub = get_pubsub_publisher()
        await pubsub.publish_call_event("call_ended", self._call_id)

        if self._telnyx_media:
            await self._telnyx_media.close()

        await session_manager.close_session(self._call_id)
        logger.info("call_completed", call_id=self._call_id)

    async def hangup(self) -> None:
        """Llamado externamente cuando Telnyx notifica hangup."""
        await self._bus.publish(EventType.CALL_HANGUP)


# Registro de orquestadores activos
_active_calls: dict[str, CallOrchestrator] = {}


def get_orchestrator(call_id: str) -> CallOrchestrator | None:
    return _active_calls.get(call_id)


async def start_call(call_id: str, caller_number: str, session_id: str, command_id: str) -> None:
    """Inicia un orquestador para una nueva llamada entrante vía Telnyx Media Streaming."""
    orchestrator = CallOrchestrator(call_id, caller_number, session_id, command_id)
    _active_calls[call_id] = orchestrator
    try:
        await orchestrator.start()
    finally:
        _active_calls.pop(call_id, None)
