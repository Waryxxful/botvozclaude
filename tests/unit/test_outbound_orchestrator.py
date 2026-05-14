from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def config():
    from src.orchestrator.outbound_orchestrator import OutboundCallConfig
    return OutboundCallConfig(
        call_id="abc-123",
        phone_number="+1",
        rendered_prompt="Hola Juan",
        greeting="Hola Juan",
        output_params=["ok"],
        webhook_url="http://django/api/v1/calls/webhook/",
    )


def test_orchestrator_stores_config(config):
    from src.orchestrator.outbound_orchestrator import OutboundOrchestrator
    orch = OutboundOrchestrator(config)
    assert orch.config.call_id == "abc-123"
    assert orch.config.output_params == ["ok"]


def test_orchestrator_uses_dynamic_system_prompt(config):
    from src.orchestrator.outbound_orchestrator import OutboundOrchestrator
    orch = OutboundOrchestrator(config)
    prompt = orch.build_system_prompt()
    assert "Hola Juan" in prompt
    assert "ok" in prompt


@pytest.mark.asyncio
@patch("src.orchestrator.outbound_orchestrator.notify_call_completed", new_callable=AsyncMock)
@patch("src.orchestrator.outbound_orchestrator.upload_call_audio", new_callable=AsyncMock, return_value="gs://b/a.wav")
async def test_finalize_uploads_audio_and_notifies_django(mock_upload, mock_notify, config):
    from src.orchestrator.outbound_orchestrator import OutboundOrchestrator
    orch = OutboundOrchestrator(config)
    orch.transcript = [
        {"role": "bot", "text": "Hola", "timestamp": 0.0},
        {"role": "client", "text": "Sí", "timestamp": 2.0},
    ]
    orch.duration_seconds = 42

    await orch.finalize(local_audio_path="/tmp/a.wav", bucket_name="bucket", webhook_timeout=10)

    mock_upload.assert_awaited_once_with(
        bucket_name="bucket", call_id="abc-123", local_path="/tmp/a.wav"
    )
    mock_notify.assert_awaited_once()
    _, kwargs = mock_notify.call_args
    assert kwargs["webhook_url"] == "http://django/api/v1/calls/webhook/"
    assert kwargs["payload"].call_id == "abc-123"
    assert kwargs["payload"].audio_gcs_url == "gs://b/a.wav"
    assert kwargs["payload"].duration_seconds == 42
