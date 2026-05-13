import pytest
from apps.scripts.parsers import parse_template, render_template

def test_parse_prompt_only():
    result = parse_template("Llama a {{nombre}} sobre {{fecha}}", "")
    assert result.input_params == ["nombre", "fecha"]
    assert result.output_params == []

def test_parse_greeting_only():
    result = parse_template("", "Hola {{nombre}} desde {{concesionaria}}")
    assert result.input_params == ["nombre", "concesionaria"]

def test_parse_combined_deduplicates():
    result = parse_template(
        prompt="Confirmar con {{nombre}} para {{fecha}} [[confirmacion]]",
        greeting="Hola {{nombre}} desde {{concesionaria}}",
    )
    assert result.input_params == ["nombre", "concesionaria", "fecha"]
    assert result.output_params == ["confirmacion"]

def test_parse_greeting_first_in_order():
    result = parse_template(
        prompt="Fecha: {{fecha}}",
        greeting="Hola {{nombre}}",
    )
    assert result.input_params == ["nombre", "fecha"]

def test_render_template_with_greeting_vars():
    rendered = render_template("Hola {{nombre}} de {{empresa}}", {"nombre": "Juan", "empresa": "Chery"})
    assert rendered == "Hola Juan de Chery"

def test_render_template_missing_value_raises():
    with pytest.raises(KeyError, match="empresa"):
        render_template("Hola {{nombre}} de {{empresa}}", {"nombre": "Juan"})
