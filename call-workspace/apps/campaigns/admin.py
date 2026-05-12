from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "script", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
