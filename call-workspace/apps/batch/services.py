"""Translate a BatchCallItem into a payload BOT_VOZ understands, and dispatch it."""

from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover — httpx not needed during tests (always mocked)
    from unittest.mock import MagicMock
    httpx = MagicMock()  # type: ignore[assignment]

from apps.scripts.parsers import OUTPUT_PATTERN, render_template


class BotVozDispatchError(RuntimeError):
    pass


_OUTPUT_INSTRUCTION_TEMPLATE = (
    "\n\n[Instrucciones del sistema] Al final de la conversación debes haber "
    "intentado recolectar los siguientes datos del cliente: {fields}. "
    "Si no lograste obtener alguno, déjalo en null. Cuando el cliente "
    "mencione fechas relativas (\"mañana\", \"el jueves\"), calcula la fecha "
    "exacta y confírmala con el cliente antes de cerrar."
)


def build_call_payload(
    *,
    call_id: str,
    phone_number: str,
    script,
    input_params: dict[str, str],
    webhook_url: str,
) -> dict[str, Any]:
    rendered_prompt = OUTPUT_PATTERN.sub("", render_template(script.prompt_template, input_params))
    rendered_greeting = render_template(script.greeting, input_params)
    if script.output_params:
        rendered_prompt += _OUTPUT_INSTRUCTION_TEMPLATE.format(
            fields=", ".join(script.output_params)
        )
    return {
        "call_id": call_id,
        "phone_number": phone_number,
        "rendered_prompt": rendered_prompt,
        "greeting": rendered_greeting,
        "output_params": list(script.output_params),
        "webhook_url": webhook_url,
    }


def dispatch_call(*, base_url: str, payload: dict, timeout: int) -> dict:
    response = httpx.post(f"{base_url.rstrip('/')}/calls/initiate", json=payload, timeout=timeout)
    if response.status_code != 200:
        raise BotVozDispatchError(
            f"BOT_VOZ returned {response.status_code}: {response.text}"
        )
    return response.json()
