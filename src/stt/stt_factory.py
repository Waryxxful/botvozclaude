"""Factory para instanciar clientes STT según configuración."""
import structlog
from typing import Union

from config.settings import get_settings
from .google_stt import GoogleSTT
from .deepgram_stt import DeepgramSTT
from .base import BaseSTT

logger = structlog.get_logger(__name__)

_stt_instance: BaseSTT | None = None


def get_stt_client() -> BaseSTT:
    """Retorna el cliente STT configurado (Google por defecto, Deepgram si está disponible)."""
    global _stt_instance

    if _stt_instance is not None:
        return _stt_instance

    settings = get_settings()

    if settings.deepgram_api_key:
        _stt_instance = DeepgramSTT()
        logger.info("stt_factory_using_deepgram")
    else:
        _stt_instance = GoogleSTT()
        logger.info("stt_factory_using_google")

    return _stt_instance


def report_stt_success(duration_ms: int = 0) -> None:
    """Registra métrica de STT exitoso. Placeholder para Prometheus."""
    if duration_ms > 0:
        logger.info("stt_success", duration_ms=duration_ms)


def report_stt_failure(error: str = "") -> None:
    """Registra métrica de error en STT. Placeholder para Prometheus."""
    logger.warning("stt_failure", error=error)
