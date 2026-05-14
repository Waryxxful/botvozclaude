"""Outbound call orchestrator driven by /calls/initiate config (not YAML profiles)."""

from dataclasses import dataclass, field

import structlog

from src.integrations.django_webhook import CallCompletedPayload, notify_call_completed
from src.integrations.gcs_audio import upload_call_audio
from src.llm.prompt_builder import build_dynamic_system_prompt

logger = structlog.get_logger(__name__)


@dataclass
class OutboundCallConfig:
    call_id: str
    phone_number: str
    rendered_prompt: str
    greeting: str
    output_params: list[str]
    webhook_url: str


class OutboundOrchestrator:
    def __init__(self, config: OutboundCallConfig):
        self.config = config
        self.transcript: list[dict] = []
        self.duration_seconds: int = 0
        self.local_audio_path: str | None = None

    def build_system_prompt(self) -> str:
        return build_dynamic_system_prompt(
            self.config.rendered_prompt, self.config.output_params
        )

    def append_turn(self, role: str, text: str, timestamp: float) -> None:
        self.transcript.append({"role": role, "text": text, "timestamp": timestamp})

    async def finalize(
        self, *, local_audio_path: str, bucket_name: str, webhook_timeout: int
    ) -> None:
        audio_url = await upload_call_audio(
            bucket_name=bucket_name,
            call_id=self.config.call_id,
            local_path=local_audio_path,
        )
        payload = CallCompletedPayload(
            call_id=self.config.call_id,
            status="completed",
            duration_seconds=self.duration_seconds,
            audio_gcs_url=audio_url,
            transcript=self.transcript,
        )
        await notify_call_completed(
            webhook_url=self.config.webhook_url,
            payload=payload,
            timeout=webhook_timeout,
        )
        logger.info("call_finalized", call_id=self.config.call_id, audio_url=audio_url)
