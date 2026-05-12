from django.urls import path

from . import views

app_name = "batch"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nuevo/", views.create_view, name="create"),
    path("<int:pk>/", views.detail_view, name="detail"),
    path("<int:pk>/progress/", views.progress_partial, name="progress"),
]
