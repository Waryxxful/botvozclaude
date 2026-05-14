from src.llm.prompt_builder import build_dynamic_system_prompt


def test_returns_prompt_unchanged_when_no_output_params():
    result = build_dynamic_system_prompt("Hola, soy un bot.", output_params=[])
    assert result == "Hola, soy un bot."


def test_appends_collection_instructions_when_output_params_present():
    result = build_dynamic_system_prompt(
        "Hola, soy un bot.", output_params=["confirmacion", "fecha"]
    )
    assert "Hola, soy un bot." in result
    assert "confirmacion" in result
    assert "fecha" in result


def test_includes_temporal_resolution_instruction():
    result = build_dynamic_system_prompt("x", output_params=["fecha"])
    assert "mañana" in result.lower() or "fecha" in result.lower()
