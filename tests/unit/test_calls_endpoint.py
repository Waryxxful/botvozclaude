"""Tests for POST /calls/initiate endpoint."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


class _AutoMockModule(types.ModuleType):
    """A module stub where any attribute access returns a MagicMock."""

    def __getattr__(self, name: str):
        mock = MagicMock()
        setattr(self, name, mock)
        return mock


def _make_auto_module(name: str) -> "_AutoMockModule":
    m = _AutoMockModule(name)
    sys.modules[name] = m
    return m


def _stub_missing_modules():
    """Stub the heavy GCP modules that aren't installed locally."""

    # Build google namespace hierarchy
    if "google" not in sys.modules:
        _make_auto_module("google")
    if "google.cloud" not in sys.modules:
        gc = _make_auto_module("google.cloud")
        sys.modules["google"].cloud = gc  # type: ignore
    else:
        gc = sys.modules["google.cloud"]

    # All google.cloud.* sub-packages need to be auto-mock modules
    gc_subs = [
        "google.cloud.firestore",
        "google.cloud.firestore_v1",
        "google.cloud.firestore_v1.async_client",
        "google.cloud.pubsub_v1",
        "google.cloud.speech",
        "google.cloud.speech_v2",
        "google.cloud.speech_v2.types",
        "google.cloud.texttospeech",
        "google.cloud.texttospeech_v1",
        "google.cloud.storage",
    ]
    for name in gc_subs:
        if name not in sys.modules:
            _make_auto_module(name)
        # Also make it accessible as an attribute of google.cloud
        short = name.replace("google.cloud.", "").split(".")[0]
        if not hasattr(sys.modules["google.cloud"], short):
            setattr(sys.modules["google.cloud"], short, sys.modules[name])

    # vertexai
    for name in ("vertexai", "vertexai.generative_models"):
        if name not in sys.modules:
            _make_auto_module(name)
    if not hasattr(sys.modules["vertexai"], "init"):
        sys.modules["vertexai"].init = MagicMock()

    # Other optional deps that may not be installed
    for name in ("webrtcvad", "soundfile", "livekit", "livekit.api", "livekit.rtc",
                 "deepgram", "telnyx", "prometheus_client", "numpy"):
        if name not in sys.modules:
            _make_auto_module(name)


# Install stubs BEFORE any src imports
_stub_missing_modules()

# Clear cached src modules to ensure fresh import with stubs
for _mod in list(sys.modules.keys()):
    if any(_mod.startswith(x) for x in ["src.api", "src.session", "src.orchestrator",
                                          "src.persistence", "src.telephony", "src.stt",
                                          "src.tts", "src.llm", "src.media"]):
        del sys.modules[_mod]


@pytest.fixture
def client():
    from src.api.app import create_app
    from fastapi.testclient import TestClient
    return TestClient(create_app())


def test_initiate_returns_bot_call_id_and_status(client):
    with patch("src.api.routes.calls.start_outbound_call_task") as mock_task:
        mock_task.return_value = None
        response = client.post(
            "/calls/initiate",
            json={
                "call_id": "abc",
                "phone_number": "+1",
                "rendered_prompt": "Hola",
                "greeting": "Hola",
                "output_params": ["ok"],
                "webhook_url": "http://django/x",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_call_id"] == "abc"
    assert body["status"] == "initiated"
    mock_task.assert_called_once()


def test_initiate_rejects_missing_fields(client):
    response = client.post(
        "/calls/initiate", json={"call_id": "abc", "phone_number": "+1"}
    )
    assert response.status_code == 422
