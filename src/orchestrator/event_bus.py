"""Bus de eventos interno basado en asyncio.Queue para desacoplar capas del pipeline."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    AUDIO_CHUNK = "audio_chunk"
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    TRANSCRIPT_INTERIM = "transcript_interim"
    TRANSCRIPT_FINAL = "transcript_final"
    LLM_TOKEN = "llm_token"
    LLM_RESPONSE_COMPLETE = "llm_response_complete"
    TOOL_CALL = "tool_call"
    TTS_START = "tts_start"
    TTS_COMPLETE = "tts_complete"
    CALL_HANGUP = "call_hangup"
    ERROR = "error"


@dataclass
class Event:
    type: EventType
    call_id: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EventBus:
    """Bus de eventos por llamada. Cada llamada tiene su propia instancia."""

    def __init__(self, call_id: str, maxsize: int = 100) -> None:
        self.call_id = call_id
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, event_type: EventType, **data) -> None:
        event = Event(type=event_type, call_id=self.call_id, data=data)
        await self._queue.put(event)

    async def consume(self) -> Event:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    def empty(self) -> bool:
        return self._queue.empty()
