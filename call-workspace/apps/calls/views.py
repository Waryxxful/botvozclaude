from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render

from apps.batch.models import BatchJob
from apps.campaigns.models import Campaign

from .models import Call, CallAnalysis
from .services.gcs_audio import generate_signed_url
from .tasks import analyze_call


@login_required
def list_view(request):
    calls = Call.objects.select_related("campaign", "analysis").all()[:100]
    return render(request, "calls/list.html", {"calls": calls})


@login_required
def detail_view(request, pk):
    call = get_object_or_404(
        Call.objects.select_related("campaign__script", "analysis"), pk=pk
    )
    audio_url = ""
    if call.audio_gcs_url:
        try:
            audio_url = generate_signed_url(call.audio_gcs_url, expires_minutes=60)
        except Exception:
            audio_url = ""
    return render(request, "calls/detail.html", {"call": call, "audio_url": audio_url})


@login_required
def reanalyze_view(request, pk):
    call = get_object_or_404(Call, pk=pk)
    call.status = "analyzing"
    call.save(update_fields=["status"])
    analyze_call.delay(str(call.id))
    return redirect("calls:detail", pk=call.pk)


@login_required
def bot_test_view(request):
    from apps.scripts.models import Script
    script_id = request.GET.get("script_id")
    script = None
    if script_id:
        try:
            script = Script.objects.get(pk=script_id)
        except Script.DoesNotExist:
            pass
    scripts = Script.objects.all()
    return render(request, "calls/bot_test.html", {
        "script": script,
        "scripts": scripts,
    })


@login_required
def dashboard_view(request):
    total_calls = Call.objects.count()
    contacted = Call.objects.filter(status="done").count()
    contact_rate = round(100 * contacted / total_calls) if total_calls else 0
    avg_score = CallAnalysis.objects.aggregate(avg=Avg("compliance_score"))["avg"] or 0
    active_batches = BatchJob.objects.filter(status="running").count()

    per_campaign = (
        Campaign.objects.annotate(
            avg_score=Avg("calls__analysis__compliance_score"),
            call_count=Count("calls"),
        )
        .filter(call_count__gt=0)
        .order_by("-avg_score")
    )

    active = (
        Campaign.objects.filter(is_active=True, script__isnull=False)
        .order_by("-updated_at")
        .first()
    )
    param_distribution: dict[str, Counter] = {}
    if active and active.script:
        analyses = CallAnalysis.objects.filter(call__campaign=active)
        for param in active.script.output_params:
            counter: Counter = Counter()
            for a in analyses:
                v = a.output_data.get(param)
                key = str(v) if v is not None else "N/R"
                counter[key] += 1
            param_distribution[param] = counter

    return render(request, "dashboard.html", {
        "total_calls": total_calls,
        "contact_rate": contact_rate,
        "avg_score": round(avg_score, 1) if avg_score else 0,
        "active_batches": active_batches,
        "per_campaign": per_campaign,
        "param_distribution": param_distribution,
        "active_campaign": active,
    })
