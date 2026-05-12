from unittest.mock import patch

import pytest

from apps.calls.models import Call, CallAnalysis
from apps.calls.services.gemini_analysis import AnalysisResult
from apps.calls.tasks import analyze_call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def call_obj(db):
    script = Script.objects.create(
        name="s",
        prompt_template="[[confirmacion]] [[fecha]]",
        greeting="hola",
    )
    campaign = Campaign.objects.create(name="c", script=script)
    return Call.objects.create(
        campaign=campaign,
        phone_number="+1",
        status="analyzing",
        transcript=[{"role": "client", "text": "sí"}],
    )


@pytest.mark.django_db
@patch("apps.calls.tasks.extract_analysis")
def test_analyze_call_creates_analysis(mock_extract, call_obj):
    mock_extract.return_value = AnalysisResult(
        output_data={"confirmacion": True, "fecha": "13 mayo"},
        summary="confirmó",
        compliance_score=9,
    )
    analyze_call(str(call_obj.id))
    call_obj.refresh_from_db()
    assert call_obj.status == "done"
    assert call_obj.analysis.output_data == {"confirmacion": True, "fecha": "13 mayo"}
    assert call_obj.analysis.compliance_score == 9


@pytest.mark.django_db
@patch("apps.calls.tasks.extract_analysis", side_effect=ValueError("bad json"))
def test_analyze_call_marks_error_on_failure(mock_extract, call_obj):
    with pytest.raises(ValueError):
        analyze_call(str(call_obj.id))
    call_obj.refresh_from_db()
    assert call_obj.status == "error"
    assert "bad json" in call_obj.error_message
