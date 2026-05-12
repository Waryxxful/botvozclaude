from django.db import models
from apps.campaigns.models import Campaign, Agent


class Call(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        TRANSCRIBING = "transcribing", "Transcribiendo"
        ANALYZING = "analyzing", "Analizando"
        DONE = "done", "Completada"
        ERROR = "error", "Error"

    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="calls")
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="calls"
    )
    ftp_path = models.CharField(max_length=1000, unique=True, verbose_name="Ruta FTP")
    audio_file = models.FileField(upload_to="audio/", blank=True, verbose_name="Archivo de audio")
    call_date = models.DateField(null=True, blank=True, verbose_name="Fecha de llamada")
    duration_seconds = models.IntegerField(null=True, blank=True, verbose_name="Duración (s)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Llamada"
        verbose_name_plural = "Llamadas"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Call {self.id} — {self.campaign.name} ({self.status})"


class Transcription(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE, related_name="transcription")
    raw_text = models.TextField(verbose_name="Transcripción")
    assemblyai_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transcripción"
        verbose_name_plural = "Transcripciones"


class ComplianceAnalysis(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE, related_name="analysis")
    # [{item: str, complied: bool}, ...]
    script_items = models.JSONField(default=list, verbose_name="Ítems del script")
    summary = models.TextField(verbose_name="Resumen")
    score = models.IntegerField(verbose_name="Puntaje")
    llm_model = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Análisis de cumplimiento"
        verbose_name_plural = "Análisis de cumplimiento"
