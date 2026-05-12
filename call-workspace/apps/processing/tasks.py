from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def poll_ftp_task(self):
    """Poll FTP directories for new recordings and enqueue processing."""
    from apps.campaigns.models import Campaign
    from apps.calls.models import Call
    from apps.processing.ftp_client import FTPClient

    client = FTPClient()
    try:
        active_campaigns = Campaign.objects.filter(is_active=True)

        for campaign in active_campaigns:
            try:
                files = client.list_audio_files(campaign.ftp_directory)
                for ftp_path, filename in files:
                    if Call.objects.filter(ftp_path=ftp_path).exists():
                        continue

                    local_rel_path = client.download_file(ftp_path, campaign.id, filename)
                    call = Call.objects.create(
                        campaign=campaign,
                        ftp_path=ftp_path,
                        audio_file=local_rel_path,
                        status=Call.Status.PENDING,
                    )
                    process_call_task.delay(call.id)
                    logger.info("Enqueued call %s from %s", call.id, ftp_path)

            except Exception as exc:
                logger.error("Campaign %s poll error: %s", campaign.id, exc)
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        client.close()


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def process_call_task(self, call_id: int):
    """Transcribe and analyze a single call recording."""
    from apps.calls.models import Call, Transcription, ComplianceAnalysis
    from apps.processing.transcription import transcribe_audio
    from apps.processing.analysis import analyze_compliance

    try:
        call = Call.objects.select_related("campaign").get(id=call_id)
    except Call.DoesNotExist:
        logger.error("Call %s not found", call_id)
        return

    try:
        # Stage 1: transcription (skip if already exists)
        try:
            transcription = call.transcription
            transcript_text = transcription.raw_text
            logger.info("Call %s: transcription already exists, skipping", call_id)
        except Transcription.DoesNotExist:
            call.status = Call.Status.TRANSCRIBING
            call.save(update_fields=["status"])
            result = transcribe_audio(str(call.audio_file.path))
            Transcription.objects.create(
                call=call,
                raw_text=result["text"],
                assemblyai_id=result["id"],
            )
            transcript_text = result["text"]

        # Stage 2: compliance analysis (skip if already exists)
        try:
            call.analysis
            logger.info("Call %s: analysis already exists, skipping", call_id)
        except ComplianceAnalysis.DoesNotExist:
            call.status = Call.Status.ANALYZING
            call.save(update_fields=["status"])
            analysis = analyze_compliance(
                transcript_text=transcript_text,
                script_text=call.campaign.script_text,
            )
            ComplianceAnalysis.objects.create(
                call=call,
                script_items=[item.model_dump() for item in analysis.script_items],
                summary=analysis.summary,
                score=analysis.score,
                llm_model=analysis.model_used,
            )
            logger.info("Call %s analysis done — score %s", call_id, analysis.score)

        call.status = Call.Status.DONE
        call.processed_at = timezone.now()
        call.save(update_fields=["status", "processed_at"])
        logger.info("Call %s done", call_id)

    except Exception as exc:
        call.status = Call.Status.ERROR
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message"])
        logger.error("Call %s failed: %s", call_id, exc)
        raise self.retry(exc=exc)
