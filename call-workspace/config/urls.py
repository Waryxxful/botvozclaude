from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve
from django.views.generic import RedirectView
from api.v1.router import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/v1/", api.urls),
    path("", RedirectView.as_view(url="/calls/dashboard/", permanent=False)),
    path("calls/", include("apps.calls.urls")),
    path("campaigns/", include("apps.campaigns.urls")),
    path("scripts/", include("apps.scripts.urls")),
    path("batch/", include("apps.batch.urls")),
    path("docs/", include("apps.docs.urls")),
    path("media/<path:path>", serve, {"document_root": settings.MEDIA_ROOT}),
]
