from django.db import models
from django.conf import settings
from apps.calls.models import Call


class CallReview(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="reviews")
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Campos flexibles: a definir con el equipo. Sin migración al agregar campos.
    extra_data = models.JSONField(default=dict, verbose_name="Datos de revisión")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Revisión"
        verbose_name_plural = "Revisiones"
        unique_together = [("call", "supervisor")]

    def __str__(self):
        return f"Review call={self.call_id} by {self.supervisor}"
