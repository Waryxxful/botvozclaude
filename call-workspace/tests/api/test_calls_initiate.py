"""Tests para POST /calls/initiate (django-ninja telephony router)."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from ninja.testing import TestClient


class _AutoMod(types.ModuleType):
    def __getattr__(self, name):
        mock = MagicMock()
        setattr(self, name, mock)
        return mock


def _stub_src_modules():
    """Mock heavy GCP/telephony modules que no están disponibles en tests."""
    def _auto(name):
        if name not in sys.modules:
            sys.modules[name] = _AutoMod(name)
        return sys.modules[name]

    for ns in ("google", "google.cloud"):
        _auto(ns)
    for sub in (
        "google.cloud.firestore", "google.cloud.pubsub_v1",
        "google.cloud.speech", "google.cloud.texttospeech_v1",
        "google.cloud.storage", "vertexai", "vertexai.generative_models",
        "webrtcvad", "deepgram",
    ):
        _auto(sub)


_stub_src_modules()


@pytest.fixture
def telephony_client():
    """TestClient del router de telefonía con deps de src.* mockeados."""
    # Limpiar módulos de src para importar frescos
    for key in list(sys.modules):
        if key.startswith(("src.orchestrator", "src.session",
                           "src.persistence", "src.telephony")):
            del sys.modules[key]

    mock_cfg = MagicMock()
    mock_cfg.environment = "development"
    mock_cfg.bot_profile = "default"

    with patch("config.settings.get_settings", return_value=mock_cfg):
        from api.v1.telephony import router
    return TestClient(router)


def test_initiate_call_returns_initiated(telephony_client):
    """POST /calls/initiate con payload completo retorna status=initiated."""
    response = telephony_client.post(
        "/calls/initiate",
        json={
            "call_id": "test-123",
            "phone_number": "+56912345678",
            "rendered_prompt": "Confirmar cita de {{nombre}}",
            "greeting": "Hola, te llamamos para confirmar",
            "output_params": ["confirmacion"],
            "webhook_url": "http://localhost:8001/api/v1/webhook/",
        },
    )
    assert response.status_code == 200
    assert response.json()["bot_call_id"] == "test-123"
    assert response.json()["status"] == "initiated"


def test_initiate_call_missing_fields(telephony_client):
    """POST /calls/initiate con campos requeridos faltantes retorna 422."""
    response = telephony_client.post(
        "/calls/initiate",
        json={"call_id": "abc", "phone_number": "+1"},
    )
    assert response.status_code == 422


def test_admin_sessions_returns_dict(telephony_client):
    """GET /admin/sessions retorna active_calls y calls."""
    response = telephony_client.get("/admin/sessions")
    assert response.status_code == 200
    body = response.json()
    assert "active_calls" in body
    assert "calls" in body


def test_admin_metrics_returns_dict(telephony_client):
    """GET /admin/metrics retorna métricas."""
    response = telephony_client.get("/admin/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "stt_calls" in body
    assert "error_rate" in body
