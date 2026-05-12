from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        SUPERVISOR = "supervisor", "Supervisor"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SUPERVISOR)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
