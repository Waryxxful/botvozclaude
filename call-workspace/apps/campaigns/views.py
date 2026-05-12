from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CampaignForm
from .models import Campaign


@login_required
def list_view(request):
    campaigns = Campaign.objects.select_related("script").all()
    return render(request, "campaigns/list.html", {"campaigns": campaigns})


@login_required
def create_view(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("campaigns:list")
    else:
        form = CampaignForm()
    return render(request, "campaigns/form.html", {"form": form, "title": "Nueva campaña"})


@login_required
def edit_view(request, pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method == "POST":
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            return redirect("campaigns:list")
    else:
        form = CampaignForm(instance=campaign)
    return render(request, "campaigns/form.html", {"form": form, "title": f"Editar: {campaign.name}"})
