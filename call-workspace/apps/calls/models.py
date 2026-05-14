import uuid

from django.db import models


class Call(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("calling", "Calling"),
        ("analyzing", "Analyzing"),
        ("done", "Done"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_item = models.ForeignKey(
        "batch.BatchCallItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.PROTECT,
        related_name="calls",
    )
    phone_number = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transcript = models.JSONField(default=list, blank=True)
    audio_gcs_url = models.CharField(max_length=500, blank=True, default="")
    duration_seconds = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    bot_call_id = models.CharField(max_length=100, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["campaign", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Call {self.id} → {self.phone_number}"


class CallAnalysis(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE, related_name="analysis")
    output_data = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True, default="")
    compliance_score = models.IntegerField(null=True, blank=True)
    llm_model = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
