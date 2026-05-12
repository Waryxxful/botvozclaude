"""Clase base abstracta para herramientas de function calling."""
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Interfaz abstracta para herramientas (function calling) del LLM."""

    @abstractmethod
    def to_gemini_function(self) -> dict[str, Any]:
        """Convierte la herramienta a declaración de función para Gemini.

        Returns:
            Dict con keys: name, description, parameters (OpenAPI schema)
        """
        ...

    @abstractmethod
    async def execute(self, call_id: str, **kwargs) -> str:
        """Ejecuta la herramienta con los parámetros dados.

        Args:
            call_id: ID de la llamada (para acceder a la sesión).
            **kwargs: Parámetros nombrados según la declaración de función.

        Returns:
            Resultado como string para enviar al LLM.
        """
        ...
