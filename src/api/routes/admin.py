"""Admin endpoints."""
import structlog
from fastapi import APIRouter

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin")


@router.get("/sessions")
async def get_sessions():
    """Lista sesiones activas."""
    # TODO: Implementar tracking de CallOrchestrator activos
    return {
        "active_calls": 0,
        "calls": [],
    }


@router.get("/metrics")
async def get_metrics():
    """Métricas de Prometheus en JSON."""
    # TODO: Exponer métricas de Prometheus
    return {
        "stt_calls": 0,
        "llm_calls": 0,
        "tts_calls": 0,
        "error_rate": 0.0,
    }
