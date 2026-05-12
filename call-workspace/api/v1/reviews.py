from ninja import Router
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.calls.models import Call
from apps.reviews.models import CallReview
from .schemas import ReviewCreateSchema, ReviewSchema

router = Router(tags=["reviews"])


@router.post("/calls/{call_id}/", response={200: ReviewSchema, 404: dict, 400: dict, 401: dict})
def upsert_review(request, call_id: int, data: ReviewCreateSchema):
    """
    **Crear o Actualizar Revisión de Supervisor**
    
    Permite al usuario logueado en la sesión (supervisor) guardar o modificar sus anotaciones
    personalizadas o la reevaluación (`score_override`) del puntaje automatizado.
    Actúa como upsert: si ya existe, lo sobrescribe.
    """
    call = get_object_or_404(Call, id=call_id)
    review, _ = CallReview.objects.update_or_create(
        call=call,
        supervisor=request.user,
        defaults={
            "extra_data": data.extra_data,
            "reviewed_at": timezone.now(),
        },
    )
    return review


@router.get("/calls/{call_id}/", response={200: ReviewSchema, 404: dict, 401: dict})
def get_review(request, call_id: int):
    """
    **Obtener Revisión del Supervisor**
    
    Retorna los datos y notas adjuntas guardadas previamente en la revisión de un humano.
    Lanzará 404 si el supervisor autenticado no ha evaluado aún la llamada.
    """
    return get_object_or_404(CallReview, call_id=call_id, supervisor=request.user)
