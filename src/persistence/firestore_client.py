import structlog
from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient

from config.settings import get_settings
from .models import CallRecord, CustomerData, TranscriptionEntry

logger = structlog.get_logger(__name__)


class FirestoreClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client: AsyncClient = firestore.AsyncClient(project=settings.gcp_project_id)
        self._calls_col = settings.firestore_calls_collection
        self._transcriptions_col = settings.firestore_transcriptions_collection
        self._customers_col = settings.firestore_customers_collection
        self._profiles_col = settings.firestore_bot_profiles_collection

    async def ping(self) -> bool:
        """Verifica conectividad con Firestore."""
        try:
            col_ref = self._client.collection(self._calls_col)
            await col_ref.limit(1).get()
            return True
        except Exception as exc:
            logger.error("firestore_ping_failed", error=str(exc))
            return False

    async def save_call(self, record: CallRecord) -> None:
        doc_ref = self._client.collection(self._calls_col).document(record.call_id)
        await doc_ref.set(record.to_firestore_dict())
        logger.info("call_saved", call_id=record.call_id, status=record.status)

    async def update_call_status(self, call_id: str, **fields) -> None:
        doc_ref = self._client.collection(self._calls_col).document(call_id)
        await doc_ref.update(fields)

    async def append_transcription(self, call_id: str, entry: TranscriptionEntry) -> None:
        doc_ref = self._client.collection(self._calls_col).document(call_id)
        await doc_ref.update({
            "transcription": firestore.ArrayUnion([entry.to_firestore_dict()])
        })

    async def save_customer(self, call_id: str, customer: CustomerData) -> None:
        doc_ref = self._client.collection(self._customers_col).document(call_id)
        await doc_ref.set({**customer.to_firestore_dict(), "call_id": call_id})
        logger.info("customer_saved", call_id=call_id)

    async def get_bot_profile(self, profile_name: str) -> dict | None:
        """Obtiene un perfil de bot desde Firestore (override de config YAML)."""
        doc_ref = self._client.collection(self._profiles_col).document(profile_name)
        doc = await doc_ref.get()
        return doc.to_dict() if doc.exists else None

    async def close(self) -> None:
        self._client.close()


_client: FirestoreClient | None = None


def get_firestore_client() -> FirestoreClient:
    global _client
    if _client is None:
        _client = FirestoreClient()
    return _client
