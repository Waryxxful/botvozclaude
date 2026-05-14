from unittest.mock import MagicMock, patch

import pytest

from apps.batch.services import BotVozDispatchError, build_call_payload, dispatch_call


def test_build_call_payload_renders_prompt_and_appends_output_instructions():
    script = MagicMock()
    script.prompt_template = "Hola {{nombre}}. Anota [[ok]]."
    script.greeting = "Hola {{nombre}}"
    script.output_params = ["ok"]

    payload = build_call_payload(
        call_id="abc-123",
        phone_number="+56912345678",
        script=script,
        input_params={"nombre": "Juan"},
        webhook_url="http://django/api/v1/calls/webhook/",
    )

    assert payload["call_id"] == "abc-123"
    assert payload["phone_number"] == "+56912345678"
    assert "Juan" in payload["rendered_prompt"]
    assert "[[ok]]" not in payload["rendered_prompt"]
    assert payload["greeting"] == "Hola Juan"
    assert payload["output_params"] == ["ok"]
    assert payload["webhook_url"] == "http://django/api/v1/calls/webhook/"


@patch("apps.batch.services.httpx.post")
def test_dispatch_call_posts_to_bot_voz(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"bot_call_id": "bot-xyz", "status": "initiated"},
    )
    result = dispatch_call(base_url="http://botvoz", payload={"call_id": "a"}, timeout=30)
    assert result == {"bot_call_id": "bot-xyz", "status": "initiated"}
    mock_post.assert_called_once_with(
        "http://botvoz/calls/initiate", json={"call_id": "a"}, timeout=30
    )


@patch("apps.batch.services.httpx.post")
def test_dispatch_call_raises_on_non_200(mock_post):
    mock_post.return_value = MagicMock(status_code=500, text="Boom")
    with pytest.raises(BotVozDispatchError, match="500"):
        dispatch_call(base_url="http://botvoz", payload={}, timeout=30)
