from django.urls import path
from . import views

app_name = "docs"

urlpatterns = [
    path("developers/", views.developers_view, name="developers"),
]
