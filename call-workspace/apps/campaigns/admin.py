from django.contrib import admin
from .models import Campaign, Agent


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "ftp_directory", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "employee_id", "is_active")
    list_filter = ("is_active", "campaigns")
    filter_horizontal = ("campaigns",)
