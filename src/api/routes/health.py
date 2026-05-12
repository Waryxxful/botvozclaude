"""Health check endpoints."""
import structlog
from datetime import datetime
from fastapi import APIRouter

from config.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check básico."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/readiness")
async def readiness_check():
    """Readiness check — verifica configuración mínima."""
    settings = get_settings()
    ready = all([
        settings.gcp_project_id,
        settings.telnyx_api_key,
    ])

    return {
        "ready": ready,
        "gcp_project_id": settings.gcp_project_id[:8] + "..." if settings.gcp_project_id else None,
        "telnyx_configured": bool(settings.telnyx_api_key),
        "environment": settings.environment,
    }
