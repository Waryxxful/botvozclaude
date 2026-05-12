from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from apps.calls.models import Call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def call_obj(db):
    s = Script.objects.create(name="s", prompt_template="x [[ok]]", greeting="hi")
    c = Campaign.objects.create(name="c", script=s)
    return Call.objects.create(
        campaign=c,
        phone_number="+1",
        status="calling",
        started_at=datetime.now(timezone.utc),
    )


@pytest.mark.django_db
@patch("api.v1.webhook.analyze_call.delay")
def test_webhook_updates_call_and_enqueues_analysis(mock_delay, client, call_obj):
    payload = {
        "call_id": str(call_obj.id),
        "status": "completed",
        "duration_seconds": 42,
        "audio_gcs_url": "gs://b/audio.wav",
        "transcript": [
            {"role": "bot", "text": "Hola", "timestamp": 0.0},
            {"role": "client", "text": "sí", "timestamp": 2.0},
        ],
    }
    response = client.post("/api/v1/calls/webhook/", data=payload, content_type="application/json")
    assert response.status_code == 200
    call_obj.refresh_from_db()
    assert call_obj.status == "analyzing"
    assert call_obj.duration_seconds == 42
    assert call_obj.audio_gcs_url == "gs://b/audio.wav"
    assert len(call_obj.transcript) == 2
    mock_delay.assert_called_once_with(str(call_obj.id))


@pytest.mark.django_db
def test_webhook_unknown_call_returns_404(client):
    response = client.post(
        "/api/v1/calls/webhook/",
        data={
            "call_id": "00000000-0000-0000-0000-000000000000",
            "status": "completed",
            "duration_seconds": 1,
            "audio_gcs_url": "",
            "transcript": [],
        },
        content_type="application/json",
    )
    assert response.status_code == 404
