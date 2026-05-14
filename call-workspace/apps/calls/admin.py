from django.contrib import admin

from .models import Call, CallAnalysis


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_number", "campaign", "status", "created_at")
    list_filter = ("status", "campaign")
    search_fields = ("phone_number",)
    readonly_fields = ("id", "created_at", "started_at", "ended_at")


@admin.register(CallAnalysis)
class CallAnalysisAdmin(admin.ModelAdmin):
    list_display = ("call", "compliance_score", "llm_model", "created_at")
