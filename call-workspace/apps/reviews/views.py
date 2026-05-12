from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from apps.calls.models import Call
from .models import CallReview


@login_required
@require_http_methods(["GET", "POST"])
def review_form(request, call_id):
    call = get_object_or_404(Call, id=call_id)
    review, _ = CallReview.objects.get_or_create(
        call=call,
        supervisor=request.user,
        defaults={"extra_data": {}},
    )

    if request.method == "POST":
        notes = request.POST.get("notes", "").strip()
        score_raw = request.POST.get("score_override", "").strip()
        review.extra_data = {
            "notes": notes,
            "score_override": int(score_raw) if score_raw.isdigit() else None,
        }
        review.reviewed_at = timezone.now()
        review.save()
        return render(request, "reviews/partials/saved.html", {"review": review})

    return render(request, "reviews/partials/form.html", {"call": call, "review": review})
