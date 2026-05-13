from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import ConversationRecording


@login_required
def list_view(request):
    recordings = ConversationRecording.objects.all()
    return render(request, "conversations/list.html", {"recordings": recordings})


@login_required
def download_view(request, pk: int):
    rec = get_object_or_404(ConversationRecording, pk=pk)
    if not rec.audio_file:
        raise Http404("Audio no disponible")
    return FileResponse(
        rec.audio_file.open("rb"),
        as_attachment=True,
        filename=f"llamada-{rec.session_id[:8]}-{rec.created_at.strftime('%Y%m%d-%H%M')}.webm",
        content_type="audio/webm",
    )
