from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class CallStatus(str, Enum):
    INITIATED = "initiated"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class TranscriptionRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class TranscriptionEntry(BaseModel):
    role: TranscriptionRole
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float | None = None
    is_final: bool = True

    def to_firestore_dict(self) -> dict:
        return {
            "role": self.role.value,
            "text": self.text,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "is_final": self.is_final,
        }


class CustomerData(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    issue: str | None = None
    extra: dict = Field(default_factory=dict)

    def to_firestore_dict(self) -> dict:
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "issue": self.issue,
            "extra": self.extra,
        }


class CallRecord(BaseModel):
    call_id: str
    caller_number: str
    bot_profile: str
    status: CallStatus = CallStatus.INITIATED
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_seconds: float | None = None
    transcription: list[TranscriptionEntry] = Field(default_factory=list)
    customer_data: CustomerData | None = None
    transferred_to: str | None = None
    metadata: dict = Field(default_factory=dict)

    def to_firestore_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "caller_number": self.caller_number,
            "bot_profile": self.bot_profile,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "transcription": [t.to_firestore_dict() for t in self.transcription],
            "customer_data": self.customer_data.to_firestore_dict() if self.customer_data else None,
            "transferred_to": self.transferred_to,
            "metadata": self.metadata,
        }
