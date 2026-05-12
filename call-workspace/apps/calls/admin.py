from django.contrib import admin
from .models import Call, Transcription, ComplianceAnalysis


class TranscriptionInline(admin.StackedInline):
    model = Transcription
    readonly_fields = ("raw_text", "assemblyai_id", "created_at")
    extra = 0


class ComplianceAnalysisInline(admin.StackedInline):
    model = ComplianceAnalysis
    readonly_fields = ("script_items", "summary", "score", "llm_model", "created_at")
    extra = 0


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "agent", "status", "created_at", "processed_at")
    list_filter = ("status", "campaign")
    search_fields = ("ftp_path",)
    readonly_fields = ("created_at", "processed_at", "ftp_path")
    inlines = [TranscriptionInline, ComplianceAnalysisInline]


@admin.register(ComplianceAnalysis)
class ComplianceAnalysisAdmin(admin.ModelAdmin):
    list_display = ("call", "score", "llm_model", "created_at")
    readonly_fields = ("created_at",)
