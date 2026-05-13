"""WebSocket consumer para el bot de prueba."""
import asyncio
import base64
import json
import struct
import uuid

import structlog
from channels.generic.websocket import AsyncWebsocketConsumer

logger = structlog.get_logger(__name__)


def _wrap_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + size, b"WAVE",
        b"fmt ", 16, 1, 1,
        sample_rate, sample_rate * 2, 2, 16,
        b"data", size,
    )
    return header + pcm


class BotTestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = str(uuid.uuid4())
        self.profile = None
        self.session = None
        self.tts = None
        self.llm = None
        self.resolved_cfg = None
        await self.accept()
        logger.info("bot_test_connected", session_id=self.session_id)

        # Cargar clientes TTS y LLM
        try:
            from src.tts.google_tts import GoogleTTS
            from src.llm.gemini_client import GeminiClient
            self.tts = GoogleTTS()
            self.llm = GeminiClient()
        except Exception as exc:
            logger.error("bot_test_init_failed", error=str(exc))
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"No se pudieron iniciar los clientes GCP: {exc}"
            }))
            await self.close()
            return

    async def disconnect(self, close_code):
        logger.info("bot_test_disconnected", session_id=self.session_id)

    async def receive(self, text_data=None, bytes_data=None):
        # Mensaje JSON (load_script, etc.)
        if text_data:
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                return

            if data.get("type") == "load_script":
                test_values = data.get("test_values", {})
                await self._load_script(
                    data.get("script_id"),
                    data.get("script_name"),
                    test_values=test_values,
                )
                return

        # Audio bytes
        if bytes_data:
            if len(bytes_data) < 400:
                await self.send(text_data=json.dumps({"type": "ready"}))
                return

            if not self.session:
                await self._init_session_default()

            await self.send(text_data=json.dumps({"type": "status", "text": "Transcribiendo..."}))
            try:
                user_text = await self._run_stt(bytes_data)
            except Exception as exc:
                await self.send(text_data=json.dumps({"type": "error", "message": f"STT: {exc}"}))
                return

            if not user_text:
                await self.send(text_data=json.dumps({
                    "type": "error", "message": "No se detectó audio. Intenta de nuevo."
                }))
                return

            await self.send(text_data=json.dumps({"type": "transcript", "text": user_text}))
            await self._build_response(user_text)

    async def _load_script(self, script_id, script_name, test_values: dict = None):
        """Loads script, renders greeting+prompt with test_values, applies resolved config."""
        try:
            from apps.scripts.models import Script
            from apps.scripts.config_resolver import resolve_agent_config
            from apps.scripts.parsers import render_template
            from config.bot_config import BotProfileSchema
            from src.session.session_state import SessionState

            script = await asyncio.get_event_loop().run_in_executor(
                None, lambda: Script.objects.get(pk=script_id)
            )
            cfg = await asyncio.get_event_loop().run_in_executor(
                None, lambda: resolve_agent_config(script)
            )

            values = test_values or {}
            try:
                greeting_rendered = render_template(script.greeting, values)
            except KeyError:
                greeting_rendered = script.greeting

            try:
                prompt_rendered = render_template(script.prompt_template, values)
            except KeyError:
                prompt_rendered = script.prompt_template

            self.profile = BotProfileSchema(
                name=f"script_{script.pk}",
                description=script.description or "",
                system_prompt=prompt_rendered,
                greeting=greeting_rendered,
                farewell="Gracias por la llamada.",
                guardrails={},
                memory={},
                tools={"enabled": []},
            )
            self.session = SessionState(
                call_id=self.session_id,
                caller_number="web-test",
                bot_profile=self.profile,
            )
            self.resolved_cfg = cfg
            logger.info("bot_test_script_loaded", script_id=script_id, name=script.name)
            await self._send_greeting()
        except Exception as exc:
            logger.warning("bot_test_script_failed", error=str(exc))
            self.resolved_cfg = None
            await self._init_session_default()

    async def _init_session_default(self):
        """Inicializa sesión con el perfil predeterminado."""
        if self.session:
            return
        try:
            from config.bot_config import get_default_profile
            from src.session.session_state import SessionState
            self.profile = get_default_profile()
            self.session = SessionState(
                call_id=self.session_id,
                caller_number="web-test",
                bot_profile=self.profile,
            )
            await self._send_greeting()
        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "error", "message": str(exc)}))

    async def _send_greeting(self):
        try:
            cfg = getattr(self, "resolved_cfg", None)
            voice = cfg.tts_voice if cfg else None
            speed = cfg.tts_speed if cfg else 1.0
            pitch = cfg.tts_pitch if cfg else 0.0
            pcm = await self.tts.synthesize(
                self.profile.greeting,
                voice=voice,
                speed=speed,
                pitch=pitch,
            )
            wav_b64 = base64.b64encode(_wrap_wav(pcm)).decode()
            await self.send(text_data=json.dumps({
                "type": "greeting",
                "text": self.profile.greeting,
                "audio": wav_b64,
            }))
        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "error", "message": f"TTS saludo: {exc}"}))

    async def _run_stt(self, audio_bytes: bytes) -> str:
        from src.stt.stt_factory import get_stt_client
        stt = get_stt_client()
        result = ""

        async def _gen():
            yield audio_bytes

        async for text, is_final in stt.transcribe_stream(_gen()):
            if text:
                result = text
            if is_final:
                break
        return result

    async def _build_response(self, user_text: str):
        from src.persistence.models import TranscriptionRole
        await self.send(text_data=json.dumps({"type": "status", "text": "Pensando..."}))

        cfg = getattr(self, "resolved_cfg", None)
        temperature = cfg.llm_temperature if cfg else None
        max_tokens = cfg.llm_max_tokens if cfg else None

        parts = []
        async for chunk in self.llm.generate_streaming(
            self.session, user_text,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            parts.append(chunk)
        response_text = "".join(parts).strip()
        self.session.add_message(TranscriptionRole.USER, user_text)
        self.session.add_message(TranscriptionRole.ASSISTANT, response_text)

        voice = cfg.tts_voice if cfg else None
        speed = cfg.tts_speed if cfg else 1.0
        pitch = cfg.tts_pitch if cfg else 0.0
        try:
            pcm = await self.tts.synthesize(response_text, voice=voice, speed=speed, pitch=pitch)
            wav_b64 = base64.b64encode(_wrap_wav(pcm)).decode()
            await self.send(text_data=json.dumps({
                "type": "response", "text": response_text, "audio": wav_b64,
            }))
        except Exception as exc:
            await self.send(text_data=json.dumps({"type": "response", "text": response_text}))
