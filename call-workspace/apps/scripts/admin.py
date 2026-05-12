from django.contrib import admin

from .models import Script


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ("name", "input_params", "output_params", "updated_at")
    search_fields = ("name",)
