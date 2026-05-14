"""Health check endpoints — django-ninja (sin autenticación)."""
from datetime import datetime, timezone

from ninja import Router, Schema
from django.http import HttpRequest

from config.settings import get_settings

router = Router()


class HealthOut(Schema):
    status: str
    timestamp: str


class ReadinessOut(Schema):
    ready: bool
    gcp_project_id: str | None
    telnyx_configured: bool
    environment: str


@router.get("/health", response=HealthOut, auth=None)
def health_check(request: HttpRequest) -> HealthOut:
    return HealthOut(status="ok", timestamp=datetime.now(timezone.utc).isoformat())


@router.get("/health/readiness", response=ReadinessOut, auth=None)
def readiness_check(request: HttpRequest) -> ReadinessOut:
    s = get_settings()
    return ReadinessOut(
        ready=bool(s.gcp_project_id and s.telnyx_api_key),
        gcp_project_id=s.gcp_project_id[:8] + "..." if s.gcp_project_id else None,
        telnyx_configured=bool(s.telnyx_api_key),
        environment=s.environment,
    )
