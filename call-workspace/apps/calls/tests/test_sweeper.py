from datetime import datetime, timedelta, timezone

import pytest

from apps.calls.models import Call
from apps.calls.tasks import sweep_orphan_calls
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def campaign(db):
    s = Script.objects.create(name="s", prompt_template="x", greeting="hi")
    return Campaign.objects.create(name="c", script=s)


@pytest.mark.django_db
def test_sweeper_marks_stuck_calls_as_error(campaign):
    old_ts = datetime.now(timezone.utc) - timedelta(minutes=15)
    stuck = Call.objects.create(
        campaign=campaign, phone_number="+1", status="calling", started_at=old_ts,
    )
    fresh = Call.objects.create(
        campaign=campaign, phone_number="+2", status="calling",
        started_at=datetime.now(timezone.utc),
    )

    swept = sweep_orphan_calls()

    stuck.refresh_from_db()
    fresh.refresh_from_db()
    assert stuck.status == "error"
    assert "orphan" in stuck.error_message.lower()
    assert fresh.status == "calling"
    assert swept == 1
