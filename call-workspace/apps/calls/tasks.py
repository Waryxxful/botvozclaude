from datetime import datetime, timedelta, timezone

from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.batch.models import BatchJob

from .models import Call, CallAnalysis
from .services.gemini_analysis import extract_analysis


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_call(self, call_id: str) -> None:
    call = Call.objects.select_related("campaign__script", "batch_item__batch_job").get(pk=call_id)
    output_params = call.campaign.script.output_params if call.campaign.script else []

    try:
        result = extract_analysis(
            transcript=call.transcript,
            output_params=output_params,
            model_name=settings.GEMINI_MODEL,
        )
    except Exception as exc:
        call.status = "error"
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message"])
        raise

    with transaction.atomic():
        CallAnalysis.objects.update_or_create(
            call=call,
            defaults={
                "output_data": result.output_data,
                "summary": result.summary,
                "compliance_score": result.compliance_score,
                "llm_model": settings.GEMINI_MODEL,
            },
        )
        call.status = "done"
        call.save(update_fields=["status"])

        if call.batch_item:
            item = call.batch_item
            item.status = "done"
            item.save(update_fields=["status"])
            job: BatchJob = item.batch_job
            BatchJob.objects.filter(pk=job.pk).update(done_calls=job.done_calls + 1)
            if job.done_calls + 1 + job.failed_calls >= job.total_calls:
                BatchJob.objects.filter(pk=job.pk).update(status="completed")


@shared_task
def sweep_orphan_calls() -> int:
    """Mark calls stuck in 'calling' status for > 10 minutes as error."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stuck = Call.objects.filter(status="calling", started_at__lt=cutoff)
    count = stuck.count()
    stuck.update(status="error", error_message="orphan call: no webhook within 10 minutes")
    return count
