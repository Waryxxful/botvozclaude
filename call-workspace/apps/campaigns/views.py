from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Count

from .models import Campaign, Agent
from .forms import CampaignForm, AgentForm


# ── Campaigns ────────────────────────────────────────────────

@login_required
def campaign_list(request):
    campaigns = (
        Campaign.objects
        .annotate(call_count=Count("calls"))
        .order_by("-created_at")
    )
    return render(request, "campaigns/list.html", {"campaigns": campaigns})


@login_required
@require_http_methods(["GET", "POST"])
def campaign_create(request):
    form = CampaignForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("campaigns:list")
    return render(request, "campaigns/form.html", {"form": form, "title": "Nueva campaña"})


@login_required
@require_http_methods(["GET", "POST"])
def campaign_edit(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    form = CampaignForm(request.POST or None, instance=campaign)
    if form.is_valid():
        form.save()
        return redirect("campaigns:list")
    return render(request, "campaigns/form.html", {
        "form": form,
        "title": f"Editar — {campaign.name}",
        "campaign": campaign,
    })


@login_required
@require_POST
def campaign_toggle(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    campaign.is_active = not campaign.is_active
    campaign.save(update_fields=["is_active"])
    label = "Activa" if campaign.is_active else "Inactiva"
    css = "bg-green-100 text-green-700" if campaign.is_active else "bg-gray-100 text-gray-500"
    return render(request, "campaigns/partials/status_badge.html", {
        "campaign": campaign, "label": label, "css": css,
    })


# ── Agents ───────────────────────────────────────────────────

@login_required
def agent_list(request):
    agents = Agent.objects.prefetch_related("campaigns").order_by("name")
    return render(request, "campaigns/agents/list.html", {"agents": agents})


@login_required
@require_http_methods(["GET", "POST"])
def agent_create(request):
    form = AgentForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("campaigns:agent_list")
    return render(request, "campaigns/agents/form.html", {"form": form, "title": "Nuevo agente"})


@login_required
@require_http_methods(["GET", "POST"])
def agent_edit(request, agent_id):
    agent = get_object_or_404(Agent, id=agent_id)
    form = AgentForm(request.POST or None, instance=agent)
    if form.is_valid():
        form.save()
        return redirect("campaigns:agent_list")
    return render(request, "campaigns/agents/form.html", {
        "form": form,
        "title": f"Editar — {agent.name}",
        "agent": agent,
    })
