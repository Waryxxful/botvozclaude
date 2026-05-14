import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.scripts.models import Script

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="u", password="p")


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_list_view_renders(client_logged_in):
    Script.objects.create(name="s1", prompt_template="x", greeting="g")
    response = client_logged_in.get(reverse("scripts:list"))
    assert response.status_code == 200
    assert b"s1" in response.content


@pytest.mark.django_db
def test_create_view_saves_and_parses(client_logged_in):
    response = client_logged_in.post(
        reverse("scripts:create"),
        {
            "name": "new-script",
            "description": "",
            "prompt_template": "Hola {{nombre}}, anota [[ok]].",
            "greeting": "Hola",
        },
    )
    assert response.status_code == 302
    script = Script.objects.get(name="new-script")
    assert script.input_params == ["nombre"]
    assert script.output_params == ["ok"]
