"""
Stub models for the batch app.
Full implementation comes in Phase 5.
"""
from django.db import models


class BatchCallItem(models.Model):
    """Placeholder model — full definition in Phase 5."""

    class Meta:
        app_label = "batch"

    def __str__(self) -> str:
        return f"BatchCallItem {self.pk}"
