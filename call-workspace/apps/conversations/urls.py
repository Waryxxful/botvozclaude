from django.urls import path
from . import views

app_name = "conversations"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("<int:pk>/download/", views.download_view, name="download"),
]
