from django.urls import path
from . import views

app_name = "calls"
urlpatterns = [
    path("", views.call_list, name="list"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("nueva/", views.upload_call, name="upload"),
    path("agentes/<int:campaign_id>/", views.campaign_agents, name="campaign_agents"),
    path("<int:call_id>/", views.call_detail, name="detail"),
    path("<int:call_id>/reprocess/", views.reprocess_call, name="reprocess"),
    path("<int:call_id>/status/", views.call_status_partial, name="status_partial"),
]
