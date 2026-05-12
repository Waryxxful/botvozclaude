from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ScriptForm
from .models import Script
from .parsers import render_template


@login_required
def list_view(request):
    scripts = Script.objects.all()
    return render(request, "scripts/list.html", {"scripts": scripts})


@login_required
def create_view(request):
    if request.method == "POST":
        form = ScriptForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("scripts:list")
    else:
        form = ScriptForm()
    return render(request, "scripts/form.html", {"form": form, "title": "Nuevo script"})


@login_required
def edit_view(request, pk: int):
    script = get_object_or_404(Script, pk=pk)
    if request.method == "POST":
        form = ScriptForm(request.POST, instance=script)
        if form.is_valid():
            form.save()
            return redirect("scripts:list")
    else:
        form = ScriptForm(instance=script)
    return render(request, "scripts/form.html", {"form": form, "title": f"Editar: {script.name}", "script": script})


@login_required
def preview_view(request, pk: int):
    script = get_object_or_404(Script, pk=pk)
    sample = {p: f"<{p}>" for p in script.input_params}
    rendered = render_template(script.prompt_template, sample)
    return render(request, "scripts/preview.html", {"script": script, "rendered": rendered, "sample": sample})
