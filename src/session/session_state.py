from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from config.bot_profiles.schema import BotProfileSchema
from src.persistence.models import TranscriptionEntry, TranscriptionRole


class TurnState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class Message:
    role: TranscriptionRole
    text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_transcription_entry(self) -> TranscriptionEntry:
        return TranscriptionEntry(role=self.role, text=self.text, timestamp=self.timestamp)


@dataclass
class SessionState:
    call_id: str
    caller_number: str
    bot_profile: BotProfileSchema
    start_time: datetime = field(default_factory=datetime.utcnow)
    turn_state: TurnState = TurnState.IDLE
    conversation_history: list[Message] = field(default_factory=list)
    customer_name: str | None = None
    customer_data: dict = field(default_factory=dict)
    transferred_to: str | None = None
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: TranscriptionRole, text: str) -> None:
        self.conversation_history.append(Message(role=role, text=text))
        # Mantener solo los últimos N turnos según config de memoria
        max_turns = self.bot_profile.memory.max_history_turns * 2  # user + assistant
        if len(self.conversation_history) > max_turns:
            self.conversation_history = self.conversation_history[-max_turns:]

    def get_history_for_llm(self) -> list[dict]:
        """Retorna el historial en formato compatible con Gemini."""
        return [
            {"role": msg.role.value, "parts": [{"text": msg.text}]}
            for msg in self.conversation_history
        ]
