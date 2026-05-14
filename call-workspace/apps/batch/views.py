import io

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .csv_validator import CsvValidationError, validate_and_parse_csv
from .forms import BatchUploadForm
from .models import BatchCallItem, BatchJob
from .tasks import process_batch_item


@login_required
def list_view(request):
    jobs = BatchJob.objects.select_related("campaign").all()
    return render(request, "batch/list.html", {"jobs": jobs})


@login_required
def create_view(request):
    if request.method == "POST":
        form = BatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            campaign = form.cleaned_data["campaign"]
            script = campaign.script
            if script is None:
                form.add_error("campaign", "Esta campaña no tiene script asignado.")
                return render(request, "batch/create.html", {"form": form})

            file_content = form.cleaned_data["csv_file"].read().decode("utf-8")
            try:
                rows = validate_and_parse_csv(io.StringIO(file_content), script.input_params)
            except CsvValidationError as exc:
                form.add_error("csv_file", str(exc))
                return render(request, "batch/create.html", {"form": form})

            job = BatchJob.objects.create(
                campaign=campaign,
                source="csv",
                total_calls=len(rows),
                status="running",
            )
            items = [
                BatchCallItem(
                    batch_job=job,
                    phone_number=r["phone_number"],
                    input_params=r["input_params"],
                )
                for r in rows
            ]
            BatchCallItem.objects.bulk_create(items)

            for item in BatchCallItem.objects.filter(batch_job=job):
                process_batch_item.delay(item.id)

            return redirect("batch:detail", pk=job.id)
    else:
        form = BatchUploadForm()
    return render(request, "batch/create.html", {"form": form})


@login_required
def detail_view(request, pk: int):
    job = get_object_or_404(
        BatchJob.objects.select_related("campaign").prefetch_related("items"),
        pk=pk,
    )
    return render(request, "batch/detail.html", {"job": job})


@login_required
def progress_partial(request, pk: int):
    job = get_object_or_404(BatchJob, pk=pk)
    pct = 0 if job.total_calls == 0 else int(100 * (job.done_calls + job.failed_calls) / job.total_calls)
    return render(request, "batch/partials/progress.html", {"job": job, "pct": pct})
