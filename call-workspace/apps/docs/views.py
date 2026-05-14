from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def developers_view(request):
    return render(request, "docs/developers.html")
