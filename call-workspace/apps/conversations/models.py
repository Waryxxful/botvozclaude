from django.db import models


class ConversationRecording(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    script_name = models.CharField(max_length=200, blank=True, default="")
    audio_file = models.FileField(upload_to="recordings/", null=True, blank=True)
    transcript = models.JSONField(default=list)
    duration_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.session_id[:8]} — {self.script_name or 'sin script'}"
