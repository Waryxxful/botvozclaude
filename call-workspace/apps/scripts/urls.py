from django.urls import path

from . import views

app_name = "scripts"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nuevo/", views.create_view, name="create"),
    path("<int:pk>/editar/", views.edit_view, name="edit"),
    path("<int:pk>/preview/", views.preview_view, name="preview"),
]
