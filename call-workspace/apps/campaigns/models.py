from django.db import models


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    script = models.ForeignKey(
        "scripts.Script",
        on_delete=models.PROTECT,
        related_name="campaigns",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name
