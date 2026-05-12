"""Pipeline principal: STT → validación guardrails → LLM → TTS."""
import asyncio
import structlog
from typing import AsyncIterator

from src.session.session_state import SessionState
from src.persistence.models import TranscriptionRole
from src.stt.stt_factory import get_stt_client, report_stt_failure, report_stt_success
from src.tts.google_tts import GoogleTTS
from src.llm.gemini_client import GeminiClient
from src.llm.function_registry import get_tools_for_profile
from .event_bus import EventBus, EventType

logger = structlog.get_logger(__name__)

_tts: GoogleTTS | None = None
_gemini: GeminiClient | None = None


def _get_tts() -> GoogleTTS:
    global _tts
    if _tts is None:
        _tts = GoogleTTS()
    return _tts


def _get_gemini() -> GeminiClient:
    global _gemini
    if _gemini is None:
        _gemini = GeminiClient()
    return _gemini


async def run_stt(audio_bytes: bytes, session: SessionState, bus: EventBus) -> str | None:
    """Transcribe audio y publica eventos de transcripción al bus."""
    stt = get_stt_client()

    async def audio_gen() -> AsyncIterator[bytes]:
        yield audio_bytes

    final_text = ""
    try:
        async for text, is_final in stt.transcribe_stream(
            audio_gen(), language=session.bot_profile.language
        ):
            if is_final:
                final_text = text
                await bus.publish(EventType.TRANSCRIPT_FINAL, text=text)
            else:
                await bus.publish(EventType.TRANSCRIPT_INTERIM, text=text)
        report_stt_success()
    except Exception as exc:
        report_stt_failure()
        logger.error("stt_pipeline_error", call_id=session.call_id, error=str(exc))
        return None

    return final_text if final_text else None


async def run_llm_and_tts(
    user_text: str,
    session: SessionState,
    bus: EventBus,
    send_audio_fn,
) -> str:
    """Ejecuta LLM (con function calling) y sintetiza la respuesta.

    Estrategia de baja latencia:
    - Si hay tool calls → usa generate_response() (no-streaming, necesita resultado completo)
    - Si no hay tools habilitadas → usa generate_streaming() + TTS paralelo por frases

    Returns:
        Texto de respuesta del bot.
    """
    profile = session.bot_profile
    tools_enabled = profile.tools.enabled

    session.add_message(TranscriptionRole.USER, user_text)

    if tools_enabled:
        # Modo con function calling: no-streaming
        response_text, tool_calls = await _get_gemini().generate_response(session, user_text)

        # Ejecutar tool calls si hay
        if tool_calls:
            tool_instances = {t.name: t for t in get_tools_for_profile(tools_enabled)}
            for tc in tool_calls:
                tool = tool_instances.get(tc["name"])
                if tool:
                    await bus.publish(EventType.TOOL_CALL, name=tc["name"], args=tc["args"])
                    result = await tool.execute(session.call_id, **tc["args"])
                    logger.info("tool_executed", call_id=session.call_id, tool=tc["name"], result=result)

            # Si hubo transfer, generar mensaje de despedida
            if session.transferred_to:
                dept = session.transferred_to
                response_text = f"Perfecto, le voy a transferir con el área de {dept}. Un momento por favor."
    else:
        # Modo sin tools: streaming para menor latencia
        response_text = ""
        sentence_buffer = ""
        await bus.publish(EventType.LLM_TOKEN)

        async for token in _get_gemini().generate_streaming(session, user_text):
            response_text += token
            sentence_buffer += token
            await bus.publish(EventType.LLM_TOKEN, token=token)

            # Enviar TTS por frases completas (al encontrar puntuación)
            if any(c in sentence_buffer for c in ".!?,;"):
                sentence = sentence_buffer.strip()
                sentence_buffer = ""
                if sentence:
                    audio = await _get_tts().synthesize(sentence, language=profile.language, voice=profile.tts_voice)
                    await send_audio_fn(audio)

        # TTS del resto del buffer
        if sentence_buffer.strip():
            audio = await _get_tts().synthesize(sentence_buffer.strip(), language=profile.language, voice=profile.tts_voice)
            await send_audio_fn(audio)

    # Para el modo con tools, sintetizar respuesta completa
    if tools_enabled and response_text:
        audio = await _get_tts().synthesize(response_text, language=profile.language, voice=profile.tts_voice)
        await send_audio_fn(audio)

    session.add_message(TranscriptionRole.ASSISTANT, response_text)
    await bus.publish(EventType.LLM_RESPONSE_COMPLETE, text=response_text)

    return response_text
