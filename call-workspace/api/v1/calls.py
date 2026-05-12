from ninja import Router
from django.shortcuts import get_object_or_404
from typing import Optional
import uuid

from apps.calls.models import Call, CallAnalysis
from .schemas import CallListSchema, CallDetailSchema, CallAnalysisSchema

router = Router(tags=["calls"])


@router.get("/", response={200: list[CallListSchema], 401: dict})
def list_calls(
    request,
    campaign_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """
    **Listar Llamadas**

    Obtiene un listado de las llamadas registradas en el sistema.
    Puede filtrarse por campaña o por estado.
    """
    qs = Call.objects.select_related("campaign").order_by("-created_at")
    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)
    if status:
        qs = qs.filter(status=status)
    return qs


@router.get("/{call_id}/", response={200: CallDetailSchema, 404: dict, 401: dict})
def get_call(request, call_id: uuid.UUID):
    """
    **Obtener Detalle de Llamada**

    Devuelve los detalles completos de una llamada específica.
    """
    return get_object_or_404(
        Call.objects.select_related("campaign", "analysis"),
        id=call_id,
    )


@router.get("/{call_id}/analysis/", response={200: CallAnalysisSchema, 404: dict, 401: dict})
def get_analysis(request, call_id: uuid.UUID):
    """
    **Obtener Análisis de Llamada**

    Extrae el análisis generado por el LLM para una llamada específica.
    Devuelve 404 si la llamada aún no ha sido analizada o no existe.
    """
    return get_object_or_404(CallAnalysis, call_id=call_id)
