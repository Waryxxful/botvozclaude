import pytest

from apps.scripts.parsers import parse_template, render_template


class TestParseTemplate:
    def test_extracts_input_params_simple(self):
        text = "Hola {{nombre}}, lo llamo por {{fecha}}."
        result = parse_template(text)
        assert result.input_params == ["nombre", "fecha"]
        assert result.output_params == []

    def test_extracts_output_params(self):
        text = "Anota [[confirmacion]] y [[nueva_fecha]] si aplica."
        result = parse_template(text)
        assert result.input_params == []
        assert result.output_params == ["confirmacion", "nueva_fecha"]

    def test_mixed_params(self):
        text = "Hola {{nombre}}. Anota [[confirmacion]]. Visita el {{fecha}}."
        result = parse_template(text)
        assert result.input_params == ["nombre", "fecha"]
        assert result.output_params == ["confirmacion"]

    def test_deduplicates_params(self):
        text = "{{nombre}}... {{nombre}} otra vez. [[ok]] [[ok]]."
        result = parse_template(text)
        assert result.input_params == ["nombre"]
        assert result.output_params == ["ok"]

    def test_ignores_single_braces(self):
        text = "Esto {no} es {param}. Pero {{si}} lo es."
        result = parse_template(text)
        assert result.input_params == ["si"]


class TestRenderTemplate:
    def test_replaces_input_params(self):
        text = "Hola {{nombre}}, hoy es {{fecha}}."
        result = render_template(text, {"nombre": "Juan", "fecha": "13 mayo"})
        assert result == "Hola Juan, hoy es 13 mayo."

    def test_leaves_output_params_untouched(self):
        text = "Hola {{nombre}}. Anota [[confirmacion]]."
        result = render_template(text, {"nombre": "Juan"})
        assert result == "Hola Juan. Anota [[confirmacion]]."

    def test_missing_param_raises(self):
        text = "Hola {{nombre}}, hoy es {{fecha}}."
        with pytest.raises(KeyError, match="fecha"):
            render_template(text, {"nombre": "Juan"})
