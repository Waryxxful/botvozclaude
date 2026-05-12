from django.db import models

from .parsers import parse_template


class Script(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    prompt_template = models.TextField()
    greeting = models.CharField(max_length=500)
    input_params = models.JSONField(default=list, blank=True)
    output_params = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        parsed = parse_template(self.prompt_template)
        self.input_params = parsed.input_params
        self.output_params = parsed.output_params
        super().save(*args, **kwargs)
