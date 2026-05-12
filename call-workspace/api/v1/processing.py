from ninja import Router
from django.conf import settings

router = Router(tags=["processing"])


@router.post("/trigger/", response={202: dict, 401: dict})
def trigger_ftp_poll(request):
    """
    **Disparar Polling Manual (FTP)**
    
    Encola en Celery una tarea explícita e inmediata de recuperación de audios (FTP Poll).
    Sirve como alternativa al Celery Beat automatizado para buscar e ingresar nuevos archivos de manera forzada.
    Devuelve HTTP 202 con el ID de la tarea disparada.
    """
    from apps.processing.tasks import poll_ftp_task
    task = poll_ftp_task.delay()
    return 202, {"task_id": task.id, "status": "enqueued"}


@router.get("/status/", response={200: dict, 401: dict})
def get_status(request):
    """
    **Estatus del Procesamiento de Subsistemas**
    
    Provee una indicación de salud (Healthcheck) mostrando el estado de ping a Redis,
    la configuración actual de FTP y el modelo LLM cargado para analizar llamadas.
    """
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.CELERY_BROKER_URL)
        redis_ok = r.ping()
    except Exception:
        redis_ok = False

    return {
        "redis": "ok" if redis_ok else "error",
        "ftp_host": settings.FTP_HOST or "not configured",
        "poll_interval_seconds": settings.FTP_POLL_INTERVAL,
        "llm_model": settings.OPENROUTER_MODEL,
    }
