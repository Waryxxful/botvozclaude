from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nueva/", views.create_view, name="create"),
    path("<int:pk>/editar/", views.edit_view, name="edit"),
]
