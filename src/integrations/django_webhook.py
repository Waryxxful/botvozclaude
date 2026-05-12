"""HTTP client that notifies Django when a call has completed."""

from dataclasses import asdict, dataclass

import httpx


class DjangoWebhookError(RuntimeError):
    pass


@dataclass
class CallCompletedPayload:
    call_id: str
    status: str
    duration_seconds: int
    audio_gcs_url: str
    transcript: list[dict]


async def notify_call_completed(
    *, webhook_url: str, payload: CallCompletedPayload, timeout: int
) -> None:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(webhook_url, json=asdict(payload))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DjangoWebhookError(f"Webhook failed: {exc}") from exc
