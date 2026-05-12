from ninja import Router, Schema
from pydantic import Field

from apps.batch.models import BatchCallItem, BatchJob
from apps.batch.tasks import process_batch_item
from apps.campaigns.models import Campaign

router = Router()


class CallItem(Schema):
    phone_number: str = Field(..., max_length=30)
    input_params: dict


class BatchCreateIn(Schema):
    campaign_id: int
    calls: list[CallItem]


class BatchCreateOut(Schema):
    batch_job_id: int
    total_calls: int
    status: str


@router.post("/", response={200: BatchCreateOut, 400: dict, 404: dict})
def create_batch(request, payload: BatchCreateIn):
    try:
        campaign = Campaign.objects.select_related("script").get(pk=payload.campaign_id, is_active=True)
    except Campaign.DoesNotExist:
        return 404, {"detail": "Campaign not found or inactive."}

    script = campaign.script
    if script is None:
        return 400, {"detail": "Campaign has no script assigned."}

    for call in payload.calls:
        missing = [p for p in script.input_params if p not in call.input_params]
        if missing:
            return 400, {"detail": f"Missing input params: {', '.join(missing)}"}

    job = BatchJob.objects.create(
        campaign=campaign,
        source="api",
        total_calls=len(payload.calls),
        status="running",
    )
    items = [
        BatchCallItem(
            batch_job=job,
            phone_number=c.phone_number,
            input_params=c.input_params,
        )
        for c in payload.calls
    ]
    BatchCallItem.objects.bulk_create(items)
    for item in BatchCallItem.objects.filter(batch_job=job):
        process_batch_item.delay(item.id)

    return 200, BatchCreateOut(batch_job_id=job.id, total_calls=job.total_calls, status="pending")
