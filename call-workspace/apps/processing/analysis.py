from __future__ import annotations
import json
import re
import httpx
from openai import OpenAI
from pydantic import BaseModel, Field
from django.conf import settings

SYSTEM_PROMPT = """Eres un evaluador de cumplimiento de scripts para un call center en Chile.
Se te entrega la transcripción de una llamada y el script que el agente debe seguir.

Tu tarea:
1. Evalúa cada ítem del script: ¿el agente lo cumplió (true) o no (false)?
2. Escribe un resumen breve (2-3 oraciones) del cumplimiento general.
3. Asigna un puntaje del 1 al 10 (10 = cumplimiento perfecto).

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura, sin texto adicional:
{"script_items": [{"item": "texto del ítem", "complied": true}], "summary": "resumen", "score": 8}"""

USER_PROMPT = """Script de cumplimiento:
---
{script}
---

Transcripción de la llamada:
---
{transcript}
---

Responde solo con el JSON:"""


class ScriptItem(BaseModel):
    item: str
    complied: bool = False


class ComplianceResult(BaseModel):
    script_items: list[ScriptItem]
    summary: str
    score: int = Field(ge=0, le=10)
    model_used: str = ""


def _extract_json(text: str) -> dict:
    if text is None:
        raise ValueError("LLM returned None instead of text")
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No valid JSON in LLM response: {text[:300]}")


def analyze_compliance(transcript_text: str, script_text: str) -> ComplianceResult:
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        http_client=httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)),
    )

    response = client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(
                script=script_text,
                transcript=transcript_text,
            )},
        ],
        temperature=0,
        max_tokens=500,
    )

    raw = response.choices[0].message.content
    data = _extract_json(raw)
    result = ComplianceResult(**data)
    result.model_used = settings.OPENROUTER_MODEL
    return result
