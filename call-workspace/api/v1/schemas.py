from ninja import Schema, Field
from typing import Optional
from datetime import datetime
import uuid


class CampaignSchema(Schema):
    id: int = Field(..., description="ID único de la campaña")
    name: str = Field(..., description="Nombre de la campaña", example="Renovaciones 2026")
    is_active: bool = Field(..., description="Indica si la campaña está activa")
    created_at: datetime = Field(..., description="Fecha de creación")


class CampaignCreateSchema(Schema):
    name: str = Field(..., description="Nombre de la campaña", example="Ventas Outbound")
    description: str = Field("", description="Descripción detallada o notas internas")
    is_active: bool = Field(True, description="Habilitar la campaña al crearla")


class CampaignUpdateSchema(Schema):
    name: Optional[str] = Field(None, description="Nombre de la campaña")
    description: Optional[str] = Field(None, description="Descripción detallada o notas internas")
    is_active: Optional[bool] = Field(None, description="Habilitar o deshabilitar la campaña")


class CallListSchema(Schema):
    id: uuid.UUID = Field(..., description="ID único de la llamada")
    campaign_name: str = Field(..., description="Nombre de la campaña asociada")
    phone_number: str = Field(..., description="Número de teléfono")
    status: str = Field(..., description="Estado de la llamada", example="done")
    created_at: datetime = Field(..., description="Fecha de registro")

    @staticmethod
    def resolve_campaign_name(obj):
        return obj.campaign.name


class CallDetailSchema(Schema):
    id: uuid.UUID = Field(..., description="ID único de la llamada")
    campaign_name: str = Field(..., description="Nombre de la campaña")
    phone_number: str = Field(..., description="Número de teléfono")
    status: str = Field(..., description="Estado de la llamada")
    error_message: str = Field(..., description="Mensaje de error si aplica")
    audio_gcs_url: str = Field(..., description="URL del audio en GCS")
    duration_seconds: Optional[int] = Field(None, description="Duración en segundos")
    bot_call_id: str = Field(..., description="ID de llamada del bot de voz")
    created_at: datetime = Field(..., description="Fecha de registro")
    started_at: Optional[datetime] = Field(None, description="Inicio de la llamada")
    ended_at: Optional[datetime] = Field(None, description="Fin de la llamada")

    @staticmethod
    def resolve_campaign_name(obj):
        return obj.campaign.name


class CallAnalysisSchema(Schema):
    id: int = Field(..., description="ID único del análisis")
    output_data: dict = Field(..., description="Datos de salida del LLM")
    summary: str = Field(..., description="Resumen generado por el LLM")
    compliance_score: Optional[int] = Field(None, description="Puntuación de cumplimiento")
    llm_model: str = Field(..., description="Modelo LLM que generó el análisis")
    created_at: datetime = Field(..., description="Fecha del análisis")


class ReviewCreateSchema(Schema):
    extra_data: dict = Field({}, description="Datos adicionales libres", example={"notes": "Faltó más claridad"})


class ReviewSchema(Schema):
    id: int = Field(..., description="ID de la revisión")
    supervisor_id: int = Field(..., description="ID del supervisor que audita")
    extra_data: dict = Field(..., description="Datos flexibles añadidos")
    reviewed_at: Optional[datetime] = None
