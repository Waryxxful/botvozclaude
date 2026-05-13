from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
import json

from .forms import ScriptForm, GlobalConfigForm
from .models import Script, AgentGlobalConfig
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
    return render(request, "scripts/form.html", {
        "form": form,
        "title": "Nuevo script",
        "gcfg": AgentGlobalConfig.get(),
    })


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
    return render(request, "scripts/form.html", {
        "form": form,
        "title": f"Editar: {script.name}",
        "script": script,
        "gcfg": AgentGlobalConfig.get(),
    })


@login_required
def global_config_view(request):
    instance = AgentGlobalConfig.get()
    if request.method == "POST":
        form = GlobalConfigForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, "Configuración global guardada.")
            return redirect("scripts:global_config")
    else:
        form = GlobalConfigForm(instance=instance)
    return render(request, "scripts/global_config.html", {"form": form})


@login_required
def preview_view(request, pk: int):
    script = get_object_or_404(Script, pk=pk)
    rendered = None
    test_data = {}
    test_data_list = []

    if request.method == "POST":
        # Obtener datos de prueba del formulario
        test_data = {p: request.POST.get(f"test_{p}", "") for p in script.input_params}
        try:
            rendered = render_template(script.prompt_template, test_data)
        except KeyError as e:
            rendered = f"Error: {e}"
    else:
        # Valores por defecto
        test_data = {p: "" for p in script.input_params}
        try:
            rendered = render_template(script.prompt_template, {p: f"<{p}>" for p in script.input_params})
        except KeyError:
            rendered = None

    # Convertir a lista para fácil acceso en template
    test_data_list = [{"param": p, "value": test_data.get(p, "")} for p in script.input_params]

    return render(
        request,
        "scripts/preview.html",
        {
            "script": script,
            "rendered": rendered,
            "test_data_list": test_data_list,
        }
    )


def script_json_view(request, pk: int):
    """Endpoint público que retorna datos del script como JSON (para bot de prueba)."""
    script = get_object_or_404(Script, pk=pk)
    return JsonResponse({
        "id": script.pk,
        "name": script.name,
        "greeting": script.greeting,
        "system_prompt": script.prompt_template,
        "input_params": script.input_params,
        "output_params": script.output_params,
    })


@login_required
def test_api_view(request, pk: int):
    """API endpoint para probar un script con datos de prueba (AJAX)."""
    script = get_object_or_404(Script, pk=pk)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            test_data = data.get("test_data", {})

            # Validar que tiene todos los parámetros
            missing = [p for p in script.input_params if p not in test_data or not test_data[p]]
            if missing:
                return JsonResponse({"error": f"Faltan valores para: {', '.join(missing)}"}, status=400)

            # Renderizar el script con los datos
            rendered = render_template(script.prompt_template, test_data)

            return JsonResponse({
                "success": True,
                "rendered": rendered,
                "input_params": script.input_params,
                "output_params": script.output_params,
            })
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)
        except KeyError as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Método no permitido"}, status=405)
