import pytest
from apps.scripts.config_resolver import ResolvedAgentConfig, resolve_agent_config


@pytest.mark.django_db
def test_resolve_uses_script_value_when_set(script_with_voice):
    cfg = resolve_agent_config(script_with_voice)
    assert cfg.tts_voice == "es-US-Neural2-B"


@pytest.mark.django_db
def test_resolve_falls_back_to_global_when_null(script_no_config):
    cfg = resolve_agent_config(script_no_config)
    assert cfg.tts_voice == "es-US-Neural2-A"
    assert cfg.tts_speed == 1.0
    assert cfg.llm_temperature == 0.5
    assert cfg.vad_silence_ms == 900


@pytest.mark.django_db
def test_resolve_partial_override(script_partial_config):
    cfg = resolve_agent_config(script_partial_config)
    assert cfg.tts_speed == 1.5
    assert cfg.tts_voice == "es-US-Neural2-A"
