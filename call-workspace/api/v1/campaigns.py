from ninja import Router
from django.shortcuts import get_object_or_404

from apps.campaigns.models import Campaign
from .schemas import CampaignSchema, CampaignCreateSchema, CampaignUpdateSchema

router = Router(tags=["campaigns"])


@router.get("/", response={200: list[CampaignSchema], 401: dict})
def list_campaigns(request):
    """
    **Listar Campañas**
    
    Devuelve la información general de todas las campañas registradas.
    Útil para crear listas desplegables o dashboards.
    """
    return Campaign.objects.all()


@router.post("/", response={201: CampaignSchema, 400: dict, 401: dict})
def create_campaign(request, data: CampaignCreateSchema):
    """
    **Crear Nueva Campaña**
    
    Adiciona una nueva campaña al sistema. Requiere definir las rutas iniciales del FTP
    y el texto del guion (`script_text`) que el LLM usará posteriormente como base para evaluar llamadas.
    """
    return 201, Campaign.objects.create(**data.dict())


@router.put("/{campaign_id}/", response={200: CampaignSchema, 404: dict, 400: dict, 401: dict})
def update_campaign(request, campaign_id: int, data: CampaignUpdateSchema):
    """
    **Actualizar Campaña**
    
    Modifica los valores de una campaña existente, incluyendo su estado (`is_active`).
    Actualización parcial soportada excluyendo del request los valores que no se deseen mutar.
    """
    campaign = get_object_or_404(Campaign, id=campaign_id)
    for field, value in data.dict(exclude_none=True).items():
        setattr(campaign, field, value)
    campaign.save()
    return campaign
