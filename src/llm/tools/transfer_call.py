"""Tool para transferir la llamada a un agente humano."""
import structlog
from typing import Any

from src.session import session_manager
from .base_tool import BaseTool

logger = structlog.get_logger(__name__)


class TransferCallTool(BaseTool):
    """Transfiere la llamada a un agente humano."""

    def to_gemini_function(self) -> dict[str, Any]:
        return {
            "name": "transfer_call",
            "description": "Transfiere la llamada a un agente humano o a un departamento específico",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Departamento a transferir (ej: 'ventas', 'soporte', 'facturación')",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Razón de la transferencia",
                    },
                },
                "required": ["department"],
            },
        }

    async def execute(self, call_id: str, **kwargs) -> str:
        """Ejecuta la transferencia de llamada."""
        department = kwargs.get("department", "general")
        reason = kwargs.get("reason", "Cliente requiere asistencia")

        session = session_manager.get_session(call_id)
        if not session:
            return f"Error: sesión no encontrada para call_id={call_id}"

        # Marcar como transferida
        session.transferred_to = department

        logger.info(
            "call_transferred",
            call_id=call_id,
            department=department,
            reason=reason,
        )

        return f"Llamada transferida a {department}. {reason}"
