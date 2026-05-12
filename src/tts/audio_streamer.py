"""Envía audio TTS en chunks a LiveKit para reducir latencia percibida."""
import asyncio
import structlog
from typing import AsyncIterator, Callable, Awaitable

logger = structlog.get_logger(__name__)

CHUNK_SIZE_BYTES = 4800  # ~100ms a 24kHz 16-bit


async def stream_audio_chunks(
    audio_bytes: bytes,
    send_fn: Callable[[bytes], Awaitable[None]],
    chunk_size: int = CHUNK_SIZE_BYTES,
    delay_between_chunks: float = 0.0,
) -> None:
    """Envía audio PCM en chunks a través de la función send_fn.

    Args:
        audio_bytes: Audio completo en PCM 16-bit.
        send_fn: Función async que recibe un chunk de bytes y lo envía (ej. LiveKit track).
        chunk_size: Tamaño de cada chunk en bytes.
        delay_between_chunks: Pausa opcional entre chunks (segundos).
    """
    total = len(audio_bytes)
    sent = 0

    for i in range(0, total, chunk_size):
        chunk = audio_bytes[i:i + chunk_size]
        await send_fn(chunk)
        sent += len(chunk)
        if delay_between_chunks > 0:
            await asyncio.sleep(delay_between_chunks)

    logger.debug("audio_stream_complete", total_bytes=total)


async def audio_bytes_to_async_iter(audio_bytes: bytes, chunk_size: int = CHUNK_SIZE_BYTES) -> AsyncIterator[bytes]:
    """Convierte bytes de audio a un AsyncIterator de chunks."""
    for i in range(0, len(audio_bytes), chunk_size):
        yield audio_bytes[i:i + chunk_size]
        await asyncio.sleep(0)  # yield control al event loop
