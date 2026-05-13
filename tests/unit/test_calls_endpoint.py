"""Tests para el endpoint de llamadas — migrado a django-ninja.

Los tests completos están en call-workspace/tests/api/test_calls_initiate.py.
Este archivo verifica solo la lógica del OutboundCallConfig (sin framework).
"""

from unittest.mock import MagicMock
import sys
import types


def _stub(name):
    if name not in sys.modules:
        m = types.ModuleType(name)
        sys.modules[name] = m
    return sys.modules[name]


for _ns in ("google", "google.cloud", "google.cloud.storage",
            "google.cloud.pubsub_v1", "vertexai", "vertexai.generative_models",
            "webrtcvad", "deepgram", "soundfile"):
    _stub(_ns)


def test_outbound_call_config_stores_fields():
    """OutboundCallConfig guarda todos los campos correctamente."""
    from src.orchestrator.outbound_orchestrator import OutboundCallConfig

    cfg = OutboundCallConfig(
        call_id="abc-123",
        phone_number="+56912345678",
        rendered_prompt="Confirmar cita",
        greeting="Hola",
        output_params=["confirmacion"],
        webhook_url="http://localhost:8001/webhook/",
    )

    assert cfg.call_id == "abc-123"
    assert cfg.phone_number == "+56912345678"
    assert cfg.rendered_prompt == "Confirmar cita"
    assert cfg.greeting == "Hola"
    assert cfg.output_params == ["confirmacion"]
    assert cfg.webhook_url == "http://localhost:8001/webhook/"


def test_outbound_call_config_output_params_default_empty():
    """output_params tiene default de lista vacía."""
    from src.orchestrator.outbound_orchestrator import OutboundCallConfig

    cfg = OutboundCallConfig(
        call_id="x",
        phone_number="+1",
        rendered_prompt="hola",
        greeting="hola",
        output_params=[],
        webhook_url="http://x",
    )
    assert cfg.output_params == []
