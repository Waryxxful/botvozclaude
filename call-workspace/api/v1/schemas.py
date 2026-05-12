from ninja import Schema, Field
from typing import Optional
from datetime import datetime


class CampaignSchema(Schema):
    id: int = Field(..., description="ID único de la campaña")
    name: str = Field(..., description="Nombre de la campaña", example="Renovaciones 2026")
    ftp_directory: str = Field(..., description="Ruta FTP para ubicar grabaciones", example="/renovaciones")
    is_active: bool = Field(..., description="Indica si la campaña está en procesamiento activo")
    created_at: datetime = Field(..., description="Fecha de creación")


class CampaignCreateSchema(Schema):
    name: str = Field(..., description="Nombre de la campaña", example="Ventas Outbound")
    description: str = Field("", description="Descripción detallada o notas internas", example="Campaña enfocada en B2B")
    ftp_directory: str = Field(..., description="Ruta FTP base", example="/outbound/ventas")
    script_text: str = Field(..., description="Guion que el agente debe seguir para validación LLM", example="1. Saludo inicial\n 2. Ofrecer descuento")


class CampaignUpdateSchema(Schema):
    name: Optional[str] = Field(None, description="Nombre de la campaña")
    description: Optional[str] = Field(None, description="Descripción detallada o notas internas")
    ftp_directory: Optional[str] = Field(None, description="Ruta FTP base")
    script_text: Optional[str] = Field(None, description="Guion que el agente debe seguir para validación LLM")
    is_active: Optional[bool] = Field(None, description="Habilitar o deshabilitar la campaña")


class CallListSchema(Schema):
    id: int = Field(..., description="ID único de la llamada")
    campaign_name: str = Field(..., description="Nombre de la campaña asociada")
    status: str = Field(..., description="Estado de procesamiento", example="done")
    created_at: datetime = Field(..., description="Fecha de ingesta al sistema")
    score: Optional[int] = Field(None, description="Puntuación de 1 a 10 calculada por LLM", example=9)

    @staticmethod
    def resolve_campaign_name(obj):
        return obj.campaign.name

    @staticmethod
    def resolve_score(obj):
        try:
            return obj.analysis.score
        except Exception:
            return None


class CallDetailSchema(Schema):
    id: int = Field(..., description="ID único de la llamada")
    campaign_name: str = Field(..., description="Nombre de la campaña")
    status: str = Field(..., description="Estado de procesamiento actual", example="done")
    error_message: str = Field(..., description="Mensaje de error en caso de fallo (vacío si exitoso)")
    created_at: datetime = Field(..., description="Fecha de ingesta")
    processed_at: Optional[datetime] = Field(None, description="Fecha de finalización del análisis")
    audio_url: str = Field(..., description="URL para reproducir o descargar el audio", example="/media/audio/call.wav")
    transcript_text: Optional[str] = Field(None, description="Texto completo de la transcripción cruda")
    score: Optional[int] = Field(None, description="Calificación 1-10 del LLM", example=9)

    @staticmethod
    def resolve_campaign_name(obj):
        return obj.campaign.name

    @staticmethod
    def resolve_audio_url(obj):
        return obj.audio_file.url if obj.audio_file else ""

    @staticmethod
    def resolve_transcript_text(obj):
        try:
            return obj.transcription.raw_text
        except Exception:
            return None

    @staticmethod
    def resolve_score(obj):
        try:
            return obj.analysis.score
        except Exception:
            return None


class ScriptItemSchema(Schema):
    item: str = Field(..., description="Regla o elemento del guion evaluado", example="El agente saludó cordialmente")
    complied: bool = Field(..., description="Indica si el agente cumplió con este punto")


class ComplianceAnalysisSchema(Schema):
    id: int = Field(..., description="ID único del análisis")
    script_items: list[ScriptItemSchema] = Field(..., description="Lista de requerimientos evaluados")
    summary: str = Field(..., description="Resumen cualitativo generado por el LLM")
    score: int = Field(..., description="Calificación del 1 al 10", example=9)
    llm_model: str = Field(..., description="Nombre del modelo que generó el análisis", example="meta-llama/llama-3.3-70b-instruct:free")
    created_at: datetime = Field(..., description="Fecha del análisis")


class ReviewCreateSchema(Schema):
    extra_data: dict = Field({}, description="Datos adicionales libres (como notas o sobreescritura de score)", example={"notes": "Faltó más claridad", "score_override": 7})


class ReviewSchema(Schema):
    id: int = Field(..., description="ID de la revisión")
    supervisor_id: int = Field(..., description="ID del supervisor que audita")
    extra_data: dict = Field(..., description="Datos flexibles añadidos")
    reviewed_at: datetime = Field(..., description="Fecha de completitud")
    id: int
    supervisor_id: int
    extra_data: dict
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
