from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseSTT(ABC):
    """Interfaz abstracta para motores de reconocimiento de voz."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        language: str = "es-419",
    ) -> AsyncIterator[tuple[str, bool]]:
        """Transcribe un stream de audio.

        Args:
            audio_chunks: Stream de chunks PCM 16-bit 16kHz.
            language: Código de idioma BCP-47.

        Yields:
            Tuplas (texto, is_final) donde is_final indica resultado definitivo.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Libera recursos del cliente STT."""
        ...
