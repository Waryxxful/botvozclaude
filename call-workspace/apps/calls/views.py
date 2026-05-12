import uuid
import json
import urllib.parse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q

from .models import Call, ComplianceAnalysis
from apps.campaigns.models import Campaign, Agent


@login_required
def dashboard(request):
    # Status counts
    status_counts = {s: 0 for s, _ in Call.Status.choices}
    for row in Call.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    total = sum(status_counts.values())

    # Done-call metrics
    analyses = list(ComplianceAnalysis.objects.select_related("call__campaign").all())
    done_count = len(analyses)

    avg_score = 0
    compliance_rate = 0
    score_dist = {"low": 0, "mid": 0, "high": 0}

    if analyses:
        scores = [a.score for a in analyses]
        avg_score = round(sum(scores) / len(scores), 1)
        for s in scores:
            if s >= 8:
                score_dist["high"] += 1
            elif s >= 5:
                score_dist["mid"] += 1
            else:
                score_dist["low"] += 1

        total_items = complied_items = 0
        for a in analyses:
            for item in a.script_items:
                total_items += 1
                if item.get("complied"):
                    complied_items += 1
        if total_items:
            compliance_rate = round(complied_items / total_items * 100, 1)

    # Per-campaign stats
    campaign_rows = (
        ComplianceAnalysis.objects
        .values("call__campaign__name")
        .annotate(avg_score=Avg("score"), calls=Count("id"))
        .order_by("-avg_score")
    )
    campaign_labels = [r["call__campaign__name"] for r in campaign_rows]
    campaign_scores = [float(r["avg_score"]) for r in campaign_rows]
    campaign_calls = [r["calls"] for r in campaign_rows]

    recent_calls = (
        Call.objects.select_related("campaign", "agent")
        .prefetch_related("analysis")
        .filter(status=Call.Status.DONE)
        .order_by("-processed_at")[:10]
    )

    return render(request, "dashboard.html", {
        "total": total,
        "done_count": done_count,
        "avg_score": avg_score,
        "compliance_rate": compliance_rate,
        "score_dist": score_dist,
        "status_counts": status_counts,
        "campaign_labels": json.dumps(campaign_labels),
        "campaign_scores": json.dumps(campaign_scores),
        "campaign_calls": json.dumps(campaign_calls),
        "recent_calls": recent_calls,
    })


@login_required
def call_list(request):
    qs = Call.objects.select_related("campaign", "agent")

    campaign_id = request.GET.get("campaign", "")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    score_min = request.GET.get("score_min", "")
    score_max = request.GET.get("score_max", "")

    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(agent__name__icontains=q) | Q(campaign__name__icontains=q))
    if date_from:
        qs = qs.filter(call_date__gte=date_from)
    if date_to:
        qs = qs.filter(call_date__lte=date_to)
    if score_min:
        qs = qs.filter(analysis__score__gte=int(score_min))
    if score_max:
        qs = qs.filter(analysis__score__lte=int(score_max))

    qs = qs.prefetch_related("analysis")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    params = {k: v for k, v in request.GET.items() if k != "page" and v}
    query_string = urllib.parse.urlencode(params)

    ctx = {
        "calls": page_obj,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "campaigns": Campaign.objects.filter(is_active=True),
        "statuses": Call.Status.choices,
        "selected_campaign": campaign_id,
        "selected_status": status,
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
        "score_min": score_min,
        "score_max": score_max,
        "query_string": query_string,
    }

    if request.headers.get("HX-Request"):
        return render(request, "calls/partials/table.html", ctx)

    return render(request, "calls/list.html", ctx)


@login_required
def call_detail(request, call_id):
    call = get_object_or_404(
        Call.objects.select_related("campaign", "agent", "transcription", "analysis"),
        id=call_id,
    )
    review = call.reviews.filter(supervisor=request.user).first()
    return render(request, "calls/detail.html", {"call": call, "review": review})


@login_required
def campaign_agents(request, campaign_id):
    agents = Agent.objects.filter(campaigns=campaign_id, is_active=True).order_by("name")
    return render(request, "calls/partials/agent_options.html", {"agents": agents})


@login_required
@require_http_methods(["GET", "POST"])
def upload_call(request):
    campaigns = Campaign.objects.filter(is_active=True)

    if request.method == "POST":
        campaign_id = request.POST.get("campaign")
        agent_id = request.POST.get("agent") or None
        call_date = request.POST.get("call_date") or None
        audio = request.FILES.get("audio")

        errors = {}
        if not campaign_id:
            errors["campaign"] = "Selecciona una campaña."
        if not audio:
            errors["audio"] = "El archivo de audio es obligatorio."
        else:
            allowed = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
            if not audio.name.lower().endswith(allowed):
                errors["audio"] = "Formato no soportado. Usa MP3, WAV, M4A, OGG o FLAC."

        if errors:
            return render(request, "calls/upload.html", {
                "campaigns": campaigns,
                "errors": errors,
                "post": request.POST,
            })

        campaign = get_object_or_404(Campaign, id=campaign_id)
        agent = get_object_or_404(Agent, id=agent_id) if agent_id else None

        call = Call.objects.create(
            campaign=campaign,
            agent=agent,
            ftp_path=f"manual/{uuid.uuid4().hex}/{audio.name}",
            audio_file=audio,
            call_date=call_date or None,
            status=Call.Status.PENDING,
        )

        from apps.processing.tasks import process_call_task
        process_call_task.delay(call.id)

        return redirect("calls:detail", call_id=call.id)

    return render(request, "calls/upload.html", {"campaigns": campaigns})


@login_required
def call_status_partial(request, call_id):
    call = get_object_or_404(
        Call.objects.select_related("campaign", "agent", "transcription", "analysis"),
        id=call_id,
    )
    return render(request, "calls/partials/status.html", {"call": call})


@login_required
@require_POST
def reprocess_call(request, call_id):
    from apps.processing.tasks import process_call_task
    call = get_object_or_404(Call, id=call_id)
    call.status = Call.Status.PENDING
    call.error_message = ""
    call.save(update_fields=["status", "error_message"])
    process_call_task.delay(call_id)
    return HttpResponse(
        '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">'
        "Pendiente</span>"
    )
