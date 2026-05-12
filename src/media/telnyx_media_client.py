"""Cliente WebSocket para Telnyx Media Streaming.

Maneja audio bidireccional (entrada/salida) directamente con Telnyx.
Audio: μ-law 8kHz (formato Telnyx PSTN estándar).
"""
import asyncio
import json
import structlog
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

logger = structlog.get_logger(__name__)

# Formato de frames Telnyx Media Streaming
TELNYX_AUDIO_SAMPLE_RATE = 8000
TELNYX_AUDIO_FORMAT = "mulaw"  # μ-law encoding
TELNYX_FRAME_DURATION_MS = 20  # 20ms frames = 160 bytes @ 8kHz


class TelnexMediaStreamingClient:
    """Cliente WebSocket para Telnyx Media Streaming API.

    Proporciona:
    - Conexión bidireccional de audio
    - Callbacks para eventos de audio
    - Manejo robusto de desconexiones
    """

    def __init__(
        self,
        call_id: str,
        session_id: str,
        command_id: str,
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
    ):
        """Inicializa el cliente.

        Args:
            call_id: ID único de la llamada (para logging)
            session_id: Session ID de Telnyx Media Streaming
            command_id: Command ID de Telnyx Media Streaming
            on_audio_chunk: Callback(audio_bytes) cuando llega audio del usuario
        """
        self._call_id = call_id
        self._session_id = session_id
        self._command_id = command_id
        self._on_audio_chunk = on_audio_chunk
        self._websocket: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None

    @property
    def media_url(self) -> str:
        """Construye la URL del WebSocket de Telnyx Media Streaming."""
        # Formato: wss://media.telnyx.com/v1/{session_id}/{command_id}
        # Para desarrollo local: ws://localhost:8081/v1/{session_id}/{command_id}
        return f"wss://media.telnyx.com/v1/{self._session_id}/{self._command_id}"

    async def connect(self) -> bool:
        """Conecta al WebSocket de Telnyx Media Streaming.

        Returns:
            True si conexión exitosa, False si falló.
        """
        try:
            logger.info(
                "telnyx_media_connecting",
                call_id=self._call_id,
                url=self.media_url,
            )

            # Conectar al WebSocket
            self._websocket = await websockets.connect(
                self.media_url,
                ping_interval=20,  # Keep-alive ping cada 20s
                ping_timeout=10,
            )

            self._connected = True
            logger.info("telnyx_media_connected", call_id=self._call_id)

            # Iniciar loop de recepción de audio
            self._receive_task = asyncio.create_task(self._receive_loop())

            return True

        except Exception as exc:
            logger.error(
                "telnyx_media_connect_failed",
                call_id=self._call_id,
                error=str(exc),
            )
            self._connected = False
            return False

    async def close(self) -> None:
        """Cierra la conexión WebSocket."""
        if self._receive_task:
            self._receive_task.cancel()

        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as exc:
                logger.warning(
                    "telnyx_media_close_error",
                    call_id=self._call_id,
                    error=str(exc),
                )

        self._connected = False
        logger.info("telnyx_media_closed", call_id=self._call_id)

    async def send_audio(self, audio_bytes: bytes) -> bool:
        """Envía audio (μ-law 8kHz) al usuario.

        Args:
            audio_bytes: Audio μ-law encoded.

        Returns:
            True si envío exitoso, False si falló.
        """
        if not self._connected or not self._websocket:
            logger.warning(
                "telnyx_media_send_not_connected",
                call_id=self._call_id,
            )
            return False

        try:
            # Formato de mensaje Telnyx Media Stream (JSON con payload base64)
            message = {
                "type": "audio",
                "payload": audio_bytes.hex(),  # Convertir a hex (alternativa a base64)
            }

            await self._websocket.send(json.dumps(message))
            return True

        except Exception as exc:
            logger.error(
                "telnyx_media_send_error",
                call_id=self._call_id,
                error=str(exc),
            )
            self._connected = False
            return False

    async def _receive_loop(self) -> None:
        """Loop continuo que recibe audio del usuario via WebSocket.

        Lee frames de audio (μ-law 8kHz) y los procesa via callback.
        """
        try:
            if not self._websocket:
                return

            async for message in self._websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("type")

                    if message_type == "audio":
                        # Audio payload: hex-encoded bytes
                        payload_hex = data.get("payload", "")
                        audio_bytes = bytes.fromhex(payload_hex)

                        # Procesar via callback
                        if self._on_audio_chunk:
                            self._on_audio_chunk(audio_bytes)

                    elif message_type == "media.start":
                        logger.info(
                            "telnyx_media_started",
                            call_id=self._call_id,
                        )

                    elif message_type == "media.stop":
                        logger.info(
                            "telnyx_media_stopped",
                            call_id=self._call_id,
                        )
                        break

                    elif message_type == "error":
                        error_msg = data.get("message", "Unknown error")
                        logger.error(
                            "telnyx_media_error",
                            call_id=self._call_id,
                            error=error_msg,
                        )

                except json.JSONDecodeError as exc:
                    logger.warning(
                        "telnyx_media_invalid_json",
                        call_id=self._call_id,
                        error=str(exc),
                    )
                except Exception as exc:
                    logger.error(
                        "telnyx_media_process_error",
                        call_id=self._call_id,
                        error=str(exc),
                    )

        except asyncio.CancelledError:
            logger.debug("telnyx_media_receive_loop_cancelled", call_id=self._call_id)

        except Exception as exc:
            logger.error(
                "telnyx_media_receive_loop_error",
                call_id=self._call_id,
                error=str(exc),
            )

        finally:
            self._connected = False
            logger.info("telnyx_media_receive_loop_ended", call_id=self._call_id)
