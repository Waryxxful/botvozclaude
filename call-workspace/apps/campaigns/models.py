from django.db import models


class Campaign(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    description = models.TextField(blank=True)
    ftp_directory = models.CharField(max_length=500, verbose_name="Directorio FTP")
    script_text = models.TextField(verbose_name="Script de cumplimiento")
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campaña"
        verbose_name_plural = "Campañas"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Agent(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    employee_id = models.CharField(max_length=50, blank=True, verbose_name="ID empleado")
    campaigns = models.ManyToManyField(Campaign, blank=True, related_name="agents")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["name"]

    def __str__(self):
        return self.name
