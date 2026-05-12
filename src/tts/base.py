from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseTTS(ABC):
    """Interfaz abstracta para motores de síntesis de voz."""

    @abstractmethod
    async def synthesize(self, text: str, language: str = "es-419", voice: str | None = None) -> bytes:
        """Sintetiza texto a audio.

        Args:
            text: Texto a sintetizar.
            language: Código de idioma BCP-47.
            voice: Nombre de la voz (override de config).

        Returns:
            Bytes de audio en formato PCM 16-bit o MP3.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Libera recursos del cliente TTS."""
        ...
