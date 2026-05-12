from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def payload():
    from src.integrations.django_webhook import CallCompletedPayload
    return CallCompletedPayload(
        call_id="abc",
        status="completed",
        duration_seconds=42,
        audio_gcs_url="gs://b/a.wav",
        transcript=[
            {"role": "bot", "text": "Hola", "timestamp": 0.0},
            {"role": "client", "text": "Sí", "timestamp": 2.0},
        ],
    )


@pytest.mark.asyncio
@patch("src.integrations.django_webhook.httpx.AsyncClient")
async def test_posts_payload_to_url(mock_client_cls, payload):
    response = MagicMock(status_code=200)
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)
    mock_client_cls.return_value = client

    from src.integrations.django_webhook import notify_call_completed
    await notify_call_completed(
        webhook_url="https://django/api/v1/calls/webhook/", payload=payload, timeout=10
    )

    client.post.assert_awaited_once()
    args, kwargs = client.post.call_args
    assert args[0] == "https://django/api/v1/calls/webhook/"
    sent = kwargs["json"]
    assert sent["call_id"] == "abc"
    assert sent["audio_gcs_url"] == "gs://b/a.wav"
    assert len(sent["transcript"]) == 2


@pytest.mark.asyncio
@patch("src.integrations.django_webhook.httpx.AsyncClient")
async def test_raises_on_non_2xx(mock_client_cls, payload):
    response = MagicMock(status_code=500, text="Boom")
    response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=response)
    )
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)
    mock_client_cls.return_value = client

    from src.integrations.django_webhook import DjangoWebhookError, notify_call_completed
    with pytest.raises(DjangoWebhookError):
        await notify_call_completed(
            webhook_url="https://django/x", payload=payload, timeout=10
        )
