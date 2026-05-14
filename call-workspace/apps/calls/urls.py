from django.urls import path

from . import views

app_name = "calls"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("bot-test/", views.bot_test_view, name="bot_test"),
    path("<uuid:pk>/", views.detail_view, name="detail"),
    path("<uuid:pk>/reanalizar/", views.reanalyze_view, name="reanalyze"),
]
