from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Call


@login_required
def list_view(request):
    calls = Call.objects.select_related("campaign", "analysis").all()[:100]
    return render(request, "calls/list.html", {"calls": calls})


@login_required
def detail_view(request, pk):
    call = get_object_or_404(Call.objects.select_related("campaign", "analysis"), pk=pk)
    return render(request, "calls/detail.html", {"call": call})


@login_required
def dashboard_view(request):
    return render(request, "dashboard.html", {})
