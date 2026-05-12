import uuid
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings

from apps.calls.models import Call

from .models import BatchCallItem
from .services import build_call_payload, dispatch_call


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_batch_item(self, item_id: int) -> None:
    item = BatchCallItem.objects.select_related("batch_job__campaign__script").get(pk=item_id)
    script = item.batch_job.campaign.script
    if script is None:
        item.status = "failed"
        item.error_message = "Campaign has no script."
        item.save(update_fields=["status", "error_message"])
        return

    call = Call.objects.create(
        id=uuid.uuid4(),
        batch_item=item,
        campaign=item.batch_job.campaign,
        phone_number=item.phone_number,
        status="calling",
        started_at=datetime.now(timezone.utc),
    )

    payload = build_call_payload(
        call_id=str(call.id),
        phone_number=item.phone_number,
        script=script,
        input_params=item.input_params,
        webhook_url=f"{settings.WEBHOOK_PUBLIC_URL}/api/v1/calls/webhook/",
    )

    item.attempts += 1
    item.called_at = datetime.now(timezone.utc)
    try:
        response = dispatch_call(
            base_url=settings.BOT_VOZ_BASE_URL,
            payload=payload,
            timeout=settings.BOT_VOZ_TIMEOUT_SECONDS,
        )
        call.bot_call_id = response.get("bot_call_id", "")
        call.save(update_fields=["bot_call_id"])
        item.status = "calling"
        item.save(update_fields=["status", "attempts", "called_at"])
    except Exception as exc:
        call.status = "error"
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message"])
        item.status = "retry"
        item.error_message = str(exc)
        item.save(update_fields=["status", "attempts", "called_at", "error_message"])
        raise
