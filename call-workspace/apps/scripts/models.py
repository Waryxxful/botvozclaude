from django.db import models
from .parsers import parse_template

TTS_VOICE_CHOICES = [
    ("es-US-Neural2-A", "Mujer — Natural (es-US-Neural2-A)"),
    ("es-US-Neural2-C", "Mujer — Formal (es-US-Neural2-C)"),
    ("es-US-Neural2-B", "Hombre — Natural (es-US-Neural2-B)"),
    ("es-US-Neural2-D", "Hombre — Formal (es-US-Neural2-D)"),
]


class AgentGlobalConfig(models.Model):
    """Singleton with default values for all scripts."""
    tts_voice = models.CharField(max_length=50, choices=TTS_VOICE_CHOICES, default="es-US-Neural2-A")
    tts_speed = models.FloatField(default=1.0)
    tts_pitch = models.FloatField(default=0.0)
    llm_temperature = models.FloatField(default=0.5)
    llm_max_tokens = models.IntegerField(default=300)
    vad_silence_ms = models.IntegerField(default=900)
    max_call_duration_seconds = models.IntegerField(default=600)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración global del agente"

    @classmethod
    def get(cls) -> "AgentGlobalConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Script(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    prompt_template = models.TextField()
    greeting = models.CharField(max_length=500)
    input_params = models.JSONField(default=list, blank=True)
    output_params = models.JSONField(default=list, blank=True)
    # Voice config (null = use global)
    tts_voice = models.CharField(max_length=50, choices=TTS_VOICE_CHOICES, null=True, blank=True)
    tts_speed = models.FloatField(null=True, blank=True)
    tts_pitch = models.FloatField(null=True, blank=True)
    # LLM config
    llm_temperature = models.FloatField(null=True, blank=True)
    llm_max_tokens = models.IntegerField(null=True, blank=True)
    # Conversation config
    vad_silence_ms = models.IntegerField(null=True, blank=True)
    max_call_duration_seconds = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        parsed = parse_template(self.prompt_template, self.greeting)
        self.input_params = parsed.input_params
        self.output_params = parsed.output_params
        super().save(*args, **kwargs)
