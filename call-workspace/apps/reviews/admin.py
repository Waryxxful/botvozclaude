from django.contrib import admin
from .models import CallReview


@admin.register(CallReview)
class CallReviewAdmin(admin.ModelAdmin):
    list_display = ("call", "supervisor", "reviewed_at", "created_at")
    list_filter = ("supervisor",)
    readonly_fields = ("created_at", "updated_at")
