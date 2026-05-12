import json
from unittest.mock import MagicMock, patch

from apps.calls.services.gemini_analysis import (
    AnalysisResult,
    build_analysis_prompt,
    extract_analysis,
)


def test_build_analysis_prompt_includes_output_params_and_transcript():
    transcript = [
        {"role": "bot", "text": "Hola Juan", "timestamp": 0.0},
        {"role": "client", "text": "Hola, sí confirmo", "timestamp": 2.0},
    ]
    prompt = build_analysis_prompt(transcript=transcript, output_params=["confirmacion", "fecha"])
    assert "confirmacion" in prompt
    assert "fecha" in prompt
    assert "Hola Juan" in prompt
    assert "Hola, sí confirmo" in prompt


@patch("apps.calls.services.gemini_analysis.GenerativeModel")
@patch("apps.calls.services.gemini_analysis.vertexai.init")
def test_extract_analysis_parses_gemini_json_response(mock_init, mock_model_cls):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "output_data": {"confirmacion": True, "fecha": "13 mayo"},
        "summary": "El cliente confirmó.",
        "compliance_score": 9,
    })
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp
    mock_model_cls.return_value = mock_model

    result = extract_analysis(
        transcript=[{"role": "client", "text": "sí"}],
        output_params=["confirmacion", "fecha"],
        model_name="gemini-2.5-pro",
    )

    assert isinstance(result, AnalysisResult)
    assert result.output_data == {"confirmacion": True, "fecha": "13 mayo"}
    assert result.summary == "El cliente confirmó."
    assert result.compliance_score == 9


@patch("apps.calls.services.gemini_analysis.GenerativeModel")
@patch("apps.calls.services.gemini_analysis.vertexai.init")
def test_extract_analysis_handles_markdown_wrapped_json(mock_init, mock_model_cls):
    mock_resp = MagicMock()
    mock_resp.text = "```json\n" + json.dumps({
        "output_data": {"x": "y"},
        "summary": "ok",
        "compliance_score": 5,
    }) + "\n```"
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp
    mock_model_cls.return_value = mock_model

    result = extract_analysis(transcript=[], output_params=["x"], model_name="gemini-2.5-pro")
    assert result.output_data == {"x": "y"}
