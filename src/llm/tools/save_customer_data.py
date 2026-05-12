"""Tool para guardar datos del cliente."""
import structlog
from typing import Any

from src.session import session_manager
from .base_tool import BaseTool

logger = structlog.get_logger(__name__)


class SaveCustomerDataTool(BaseTool):
    """Guarda datos del cliente en Firestore."""

    def to_gemini_function(self) -> dict[str, Any]:
        return {
            "name": "save_customer_data",
            "description": "Guarda información del cliente en el sistema (nombre, email, respuesta, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Campo a guardar (ej: 'contact_confirmed', 'contact_date', 'customer_name')",
                    },
                    "value": {
                        "type": "string",
                        "description": "Valor del campo",
                    },
                },
                "required": ["key", "value"],
            },
        }

    async def execute(self, call_id: str, **kwargs) -> str:
        """Ejecuta la herramienta de guardar datos del cliente."""
        key = kwargs.get("key")
        value = kwargs.get("value")

        if not key or not value:
            return "Error: key y value son requeridos"

        session = session_manager.get_session(call_id)
        if not session:
            return f"Error: sesión no encontrada para call_id={call_id}"

        # Guardar en la sesión (en memoria)
        session.customer_data[key] = value

        logger.info(
            "customer_data_saved",
            call_id=call_id,
            key=key,
            value=value,
        )

        return f"Datos guardados: {key}={value}"
