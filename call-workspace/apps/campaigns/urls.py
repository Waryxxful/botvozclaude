from django.urls import path
from . import views

app_name = "campaigns"
urlpatterns = [
    path("", views.campaign_list, name="list"),
    path("nueva/", views.campaign_create, name="create"),
    path("<int:campaign_id>/editar/", views.campaign_edit, name="edit"),
    path("<int:campaign_id>/toggle/", views.campaign_toggle, name="toggle"),
    path("agentes/", views.agent_list, name="agent_list"),
    path("agentes/nuevo/", views.agent_create, name="agent_create"),
    path("agentes/<int:agent_id>/editar/", views.agent_edit, name="agent_edit"),
]
