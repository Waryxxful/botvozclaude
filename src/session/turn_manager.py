"""Máquina de estados para el manejo de turnos en la conversación."""
import asyncio
import structlog
from .session_state import SessionState, TurnState

logger = structlog.get_logger(__name__)


class TurnManager:
    """Controla el flujo de turnos (IDLE → LISTENING → PROCESSING → SPEAKING → IDLE).

    Soporta barge-in: si el usuario empieza a hablar mientras el bot está hablando,
    se cancela la tarea de TTS en curso.
    """

    def __init__(self, session: SessionState) -> None:
        self._session = session
        self._tts_task: asyncio.Task | None = None
        self._barge_in_event = asyncio.Event()

    @property
    def state(self) -> TurnState:
        return self._session.turn_state

    def _set_state(self, new_state: TurnState) -> None:
        old = self._session.turn_state
        self._session.turn_state = new_state
        logger.debug("turn_state_change", call_id=self._session.call_id, from_=old, to=new_state)

    def on_speech_start(self) -> bool:
        """Llamado cuando el VAD detecta inicio de habla del usuario.

        Returns:
            True si se produjo barge-in (interrumpió al bot hablando).
        """
        if self.state == TurnState.SPEAKING:
            logger.info("barge_in_detected", call_id=self._session.call_id)
            self._barge_in_event.set()
            if self._tts_task and not self._tts_task.done():
                self._tts_task.cancel()
            self._set_state(TurnState.LISTENING)
            return True

        if self.state == TurnState.IDLE:
            self._set_state(TurnState.LISTENING)
        return False

    def on_speech_end(self) -> bool:
        """Llamado cuando el VAD detecta fin de habla del usuario.

        Returns:
            True si el sistema está listo para procesar.
        """
        if self.state == TurnState.LISTENING:
            self._set_state(TurnState.PROCESSING)
            return True
        return False

    def on_processing_start(self) -> None:
        self._set_state(TurnState.PROCESSING)

    def on_speaking_start(self, tts_task: asyncio.Task) -> None:
        self._tts_task = tts_task
        self._barge_in_event.clear()
        self._set_state(TurnState.SPEAKING)

    def on_speaking_end(self) -> None:
        self._tts_task = None
        self._set_state(TurnState.IDLE)

    async def wait_for_barge_in(self) -> None:
        """Espera a que el usuario interrumpa (para uso en tarea de TTS)."""
        await self._barge_in_event.wait()

    def is_ready_to_listen(self) -> bool:
        return self.state == TurnState.IDLE
