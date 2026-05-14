import pytest

from apps.scripts.models import Script


@pytest.mark.django_db
class TestScriptModel:
    def test_parses_input_and_output_params_on_save(self):
        s = Script.objects.create(
            name="confirm-visit",
            prompt_template="Hola {{nombre}}, confirma [[asistencia]] para el {{fecha}}.",
            greeting="Hola {{nombre}}",
        )
        s.refresh_from_db()
        assert s.input_params == ["nombre", "fecha"]
        assert s.output_params == ["asistencia"]

    def test_reparses_on_update(self):
        s = Script.objects.create(
            name="x",
            prompt_template="{{a}} [[b]]",
            greeting="hola",
        )
        s.prompt_template = "{{c}} [[d]]"
        s.save()
        s.refresh_from_db()
        assert s.input_params == ["c"]
        assert s.output_params == ["d"]

    def test_str_returns_name(self):
        s = Script(name="my-script", prompt_template="x", greeting="y")
        assert str(s) == "my-script"
