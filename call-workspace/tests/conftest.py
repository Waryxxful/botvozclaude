import pytest
from apps.scripts.models import Script, AgentGlobalConfig


@pytest.fixture(autouse=True)
def global_config(db):
    AgentGlobalConfig.objects.get_or_create(pk=1)


@pytest.fixture
def script_with_voice(db):
    return Script.objects.create(
        name="test_voice", prompt_template="hola [[ok]]",
        greeting="hi", tts_voice="es-US-Neural2-B"
    )


@pytest.fixture
def script_no_config(db):
    return Script.objects.create(
        name="test_no_config", prompt_template="hola [[ok]]", greeting="hi"
    )


@pytest.fixture
def script_partial_config(db):
    return Script.objects.create(
        name="test_partial", prompt_template="hola [[ok]]",
        greeting="hi", tts_speed=1.5
    )
