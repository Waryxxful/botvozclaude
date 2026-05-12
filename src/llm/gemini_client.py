import structlog
from typing import AsyncIterator

import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig,
    Content,
    Part,
    Tool,
    FunctionDeclaration,
)

from config.settings import get_settings
from src.session.session_state import SessionState
from .prompt_builder import build_system_prompt
from .function_registry import get_tools_for_profile, get_gemini_function_declarations

logger = structlog.get_logger(__name__)

MODEL_ID = "gemini-2.0-flash-001"


class GeminiClient:
    def __init__(self) -> None:
        settings = get_settings()
        vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
        self._generation_config = GenerationConfig(
            temperature=0.7,
            max_output_tokens=512,
            top_p=0.9,
        )

    def _build_tools(self, session: SessionState) -> list[Tool] | None:
        enabled = session.bot_profile.tools.enabled
        if not enabled:
            return None

        tool_list = get_tools_for_profile(enabled)
        declarations = get_gemini_function_declarations(tool_list)

        return [Tool(function_declarations=[
            FunctionDeclaration(
                name=d["name"],
                description=d["description"],
                parameters=d["parameters"],
            )
            for d in declarations
        ])]

    async def generate_response(
        self,
        session: SessionState,
        user_text: str,
    ) -> tuple[str, list[dict]]:
        """Genera respuesta completa (no-streaming).

        Returns:
            Tupla (texto_respuesta, lista_de_tool_calls)
        """
        system_prompt = build_system_prompt(session)
        tools = self._build_tools(session)

        model = GenerativeModel(
            model_name=MODEL_ID,
            system_instruction=system_prompt,
            tools=tools,
            generation_config=self._generation_config,
        )

        history = [
            Content(role=msg["role"], parts=[Part.from_text(msg["parts"][0]["text"])])
            for msg in session.get_history_for_llm()
        ]

        chat = model.start_chat(history=history)

        try:
            response = await chat.send_message_async(user_text)
            candidate = response.candidates[0]

            tool_calls = []
            text_parts = []

            for part in candidate.content.parts:
                if part.function_call.name:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args),
                    })
                elif part.text:
                    text_parts.append(part.text)

            response_text = " ".join(text_parts).strip()
            logger.info(
                "gemini_response",
                call_id=session.call_id,
                text_length=len(response_text),
                tool_calls=len(tool_calls),
            )
            return response_text, tool_calls

        except Exception as exc:
            logger.error("gemini_error", call_id=session.call_id, error=str(exc))
            raise

    async def generate_streaming(
        self,
        session: SessionState,
        user_text: str,
    ) -> AsyncIterator[str]:
        """Genera respuesta en streaming para reducir latencia de TTS."""
        system_prompt = build_system_prompt(session)

        model = GenerativeModel(
            model_name=MODEL_ID,
            system_instruction=system_prompt,
            generation_config=self._generation_config,
        )

        history = [
            Content(role=msg["role"], parts=[Part.from_text(msg["parts"][0]["text"])])
            for msg in session.get_history_for_llm()
        ]

        chat = model.start_chat(history=history)

        try:
            async for chunk in await chat.send_message_async(user_text, stream=True):
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        yield part.text
        except Exception as exc:
            logger.error("gemini_streaming_error", call_id=session.call_id, error=str(exc))
            raise
