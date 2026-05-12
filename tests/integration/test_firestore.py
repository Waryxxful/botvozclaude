"""Tests de integración contra Firestore real (requiere credenciales GCP)."""
import pytest
from datetime import datetime

pytestmark = pytest.mark.integration  # Saltar en CI sin credenciales


@pytest.mark.asyncio
async def test_save_and_retrieve_call(sample_session):
    from src.persistence.firestore_client import get_firestore_client
    from src.persistence.models import CallRecord, CallStatus

    record = CallRecord(
        call_id="integration-test-001",
        caller_number="+5491100000000",
        bot_profile="test",
        status=CallStatus.COMPLETED,
        start_time=datetime.utcnow(),
    )

    firestore = get_firestore_client()
    await firestore.save_call(record)

    # Verificar que existe
    doc = await firestore._client.collection(firestore._calls_col).document(record.call_id).get()
    assert doc.exists
    assert doc.to_dict()["call_id"] == "integration-test-001"

    # Limpiar
    await firestore._client.collection(firestore._calls_col).document(record.call_id).delete()
