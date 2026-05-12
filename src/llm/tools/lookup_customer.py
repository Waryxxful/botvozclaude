"""Tool para buscar información del cliente."""
import structlog
import json
from typing import Any

from src.session import session_manager
from src.persistence.firestore_client import get_firestore_client
from .base_tool import BaseTool

logger = structlog.get_logger(__name__)


class LookupCustomerTool(BaseTool):
    """Busca información del cliente en Firestore."""

    def to_gemini_function(self) -> dict[str, Any]:
        return {
            "name": "lookup_customer",
            "description": "Busca información del cliente en el sistema (historial de llamadas, datos previos, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "ID del cliente (puede ser el número de teléfono u otro identificador)",
                    },
                },
                "required": ["customer_id"],
            },
        }

    async def execute(self, call_id: str, **kwargs) -> str:
        """Busca información del cliente."""
        customer_id = kwargs.get("customer_id")

        if not customer_id:
            return "Error: customer_id es requerido"

        # Buscar en Firestore
        try:
            firestore = get_firestore_client()
            doc = await firestore._client.collection("customers").document(customer_id).get()

            if doc.exists:
                data = doc.to_dict()
                logger.info(
                    "customer_lookup_found",
                    call_id=call_id,
                    customer_id=customer_id,
                )
                return json.dumps(data, default=str, ensure_ascii=False)
            else:
                logger.info(
                    "customer_lookup_not_found",
                    call_id=call_id,
                    customer_id=customer_id,
                )
                return f"Cliente no encontrado: {customer_id}"

        except Exception as exc:
            logger.error(
                "customer_lookup_error",
                call_id=call_id,
                customer_id=customer_id,
                error=str(exc),
            )
            return f"Error al buscar cliente: {str(exc)}"
