from ninja import Router
from django.shortcuts import get_object_or_404
from typing import Optional

from apps.calls.models import Call, ComplianceAnalysis
from .schemas import CallListSchema, CallDetailSchema, ComplianceAnalysisSchema

router = Router(tags=["calls"])


@router.get("/", response={200: list[CallListSchema], 401: dict})
def list_calls(
    request,
    campaign_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """
    **Listar Llamadas**
    
    Obtiene un listado de todas las llamadas ingresadas en el sistema.
    Puede filtrarse opcionalmente por la ID de la campaña o por el estatus de procesamiento (`pending`, `transcribing`, `analyzing`, `done`, `error`).
    No incluye el texto ni análisis completo para aligerar la respuesta.
    Requiere que el usuario esté autenticado.
    """
    qs = Call.objects.select_related("campaign", "agent").order_by("-created_at")
    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)
    if status:
        qs = qs.filter(status=status)
    return qs


@router.get("/{call_id}/", response={200: CallDetailSchema, 404: dict, 401: dict})
def get_call(request, call_id: int):
    """
    **Obtener Detalle de Llamada**
    
    Devuelve los detalles completos de una llamada en específico.
    Incluye la transcripción (si la hay) y la URL del audio.
    Si la llamada no existe, retorna 404.
    """
    return get_object_or_404(
        Call.objects.select_related("campaign", "agent", "transcription", "analysis"),
        id=call_id,
    )


@router.get("/{call_id}/analysis/", response={200: ComplianceAnalysisSchema, 404: dict, 401: dict})
def get_analysis(request, call_id: int):
    """
    **Obtener Análisis de Cumplimiento**
    
    Extrae exclusivamente el análisis autogenerado por el modelo LLM para una llamada específica,
    incluyendo el score, resumen y checkboxes (script items).
    Devuelve 404 si la llamada aún no ha sido analizada o no existe.
    """
    return get_object_or_404(ComplianceAnalysis, call_id=call_id)
