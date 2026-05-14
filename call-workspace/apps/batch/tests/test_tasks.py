from unittest.mock import patch

import pytest

from apps.batch.models import BatchCallItem, BatchJob
from apps.batch.tasks import process_batch_item
from apps.calls.models import Call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def script(db):
    return Script.objects.create(
        name="s",
        prompt_template="Hola {{nombre}}. Anota [[ok]].",
        greeting="Hola {{nombre}}",
    )


@pytest.fixture
def campaign(db, script):
    return Campaign.objects.create(name="c", script=script)


@pytest.fixture
def batch_job(db, campaign):
    return BatchJob.objects.create(campaign=campaign, source="api", total_calls=1, status="running")


@pytest.mark.django_db
@patch("apps.batch.tasks.dispatch_call")
def test_process_batch_item_creates_call_and_dispatches(mock_dispatch, batch_job):
    mock_dispatch.return_value = {"bot_call_id": "bot-1", "status": "initiated"}
    item = BatchCallItem.objects.create(
        batch_job=batch_job, phone_number="+1", input_params={"nombre": "Juan"}
    )

    process_batch_item(item.id)

    item.refresh_from_db()
    assert item.status == "calling"
    call = Call.objects.get(batch_item=item)
    assert call.status == "calling"
    assert call.bot_call_id == "bot-1"
    mock_dispatch.assert_called_once()


@pytest.mark.django_db
@patch("apps.batch.tasks.dispatch_call", side_effect=Exception("network"))
def test_process_batch_item_marks_retry_on_failure(mock_dispatch, batch_job):
    item = BatchCallItem.objects.create(
        batch_job=batch_job, phone_number="+1", input_params={"nombre": "Juan"}
    )
    with pytest.raises(Exception):
        process_batch_item(item.id)
    item.refresh_from_db()
    assert item.status == "retry"
    assert item.attempts == 1
