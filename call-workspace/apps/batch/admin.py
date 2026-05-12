from django.contrib import admin

from .models import BatchCallItem, BatchJob


@admin.register(BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "source", "total_calls", "done_calls", "status", "created_at")
    list_filter = ("status", "source")


@admin.register(BatchCallItem)
class BatchCallItemAdmin(admin.ModelAdmin):
    list_display = ("id", "batch_job", "phone_number", "status")
    list_filter = ("status",)
