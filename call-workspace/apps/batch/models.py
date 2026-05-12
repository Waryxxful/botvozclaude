from django.db import models


class BatchJob(models.Model):
    SOURCE_CHOICES = [("csv", "CSV upload"), ("api", "REST API")]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.PROTECT, related_name="batch_jobs")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    total_calls = models.IntegerField(default=0)
    done_calls = models.IntegerField(default=0)
    failed_calls = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class BatchCallItem(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("calling", "Calling"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("retry", "Retry"),
    ]

    batch_job = models.ForeignKey(BatchJob, on_delete=models.CASCADE, related_name="items")
    phone_number = models.CharField(max_length=30)
    input_params = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, default="")
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["batch_job", "status"])]
