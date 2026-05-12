"""Lógica de enrutamiento: determina qué perfil de bot usar para cada llamada."""
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)

# Horario de atención (hora local configurada en GCP)
BUSINESS_HOURS_START = 8   # 8:00 AM
BUSINESS_HOURS_END = 20    # 8:00 PM


def get_profile_for_call(caller_number: str, called_number: str) -> str:
    """Determina el perfil de bot según el número llamado y horario.

    Extensible: agregar lógica de IVR, segmentación por número, etc.
    """
    now = datetime.utcnow()
    hour = now.hour

    if not (BUSINESS_HOURS_START <= hour < BUSINESS_HOURS_END):
        logger.info("call_outside_business_hours", caller=caller_number, hour=hour)
        return "fuera_de_horario"  # Perfil que informa el horario y despide

    # Por defecto: perfil de atención al cliente
    return "default"
