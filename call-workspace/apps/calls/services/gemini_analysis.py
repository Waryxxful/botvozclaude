"""Post-call analysis: feed transcript to Gemini, get structured JSON back."""

import json
import re
from dataclasses import dataclass

import vertexai
from django.conf import settings
from vertexai.generative_models import GenerativeModel


@dataclass(frozen=True)
class AnalysisResult:
    output_data: dict
    summary: str
    compliance_score: int


_SYSTEM_INSTRUCTION = (
    "Eres un analista de llamadas. Recibirás el transcript de una llamada entre "
    "un bot y un cliente. Debes responder ÚNICAMENTE con un objeto JSON válido con "
    "exactamente estas claves: output_data (objeto con los datos pedidos, null si no "
    "se obtuvieron), summary (resumen en español de 2-3 oraciones), compliance_score "
    "(entero 1-10, qué tan bien el bot siguió el objetivo de la llamada)."
)


def build_analysis_prompt(*, transcript: list[dict], output_params: list[str]) -> str:
    transcript_text = "\n".join(
        f"{turn['role'].upper()}: {turn['text']}" for turn in transcript
    )
    fields = ", ".join(output_params) if output_params else "(ninguno)"
    return (
        f"Datos a extraer (claves del JSON output_data): {fields}\n\n"
        f"Transcript de la llamada:\n{transcript_text}\n\n"
        "Responde con el JSON pedido."
    )


def extract_analysis(
    *,
    transcript: list[dict],
    output_params: list[str],
    model_name: str,
) -> AnalysisResult:
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)
    model = GenerativeModel(model_name, system_instruction=[_SYSTEM_INSTRUCTION])
    response = model.generate_content(
        build_analysis_prompt(transcript=transcript, output_params=output_params),
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )
    raw = response.text or ""
    payload = _parse_json(raw)
    return AnalysisResult(
        output_data=payload.get("output_data") or {},
        summary=payload.get("summary", ""),
        compliance_score=int(payload.get("compliance_score") or 0),
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text)
