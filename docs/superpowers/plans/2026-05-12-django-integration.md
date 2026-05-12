# Plan A — Django Integration (Control Plane) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `call-workspace` from a passive call-analysis platform into the control plane of the voice bot system: scripts management with `{{}}`/`[[]]` syntax, batch calling, automatic post-call Gemini analysis, and dashboards. SQL Server replaces PostgreSQL; AssemblyAI/OpenRouter/FTP are removed.

**Architecture:** Django + SQL Server + Celery + Redis + HTMX + Chart.js. Communicates with BOT_VOZ (FastAPI microservice) via `POST /calls/initiate` for outbound calls and receives `POST /api/v1/calls/webhook/` callbacks with transcript + GCS audio URL. All AI uses Gemini 2.5 (Vertex AI).

**Tech Stack:** Django 5.1, mssql-django, django-ninja, Celery 5, google-cloud-aiplatform (Vertex AI), google-cloud-storage, httpx, pandas (CSV).

---

## File Structure

**New files (Django):**

```
call-workspace/
├── apps/
│   ├── scripts/                       NEW APP
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py                  Script model
│   │   ├── parsers.py                 Pure-function parser for {{}} / [[]]
│   │   ├── forms.py                   ScriptForm
│   │   ├── views.py                   list, create, edit, preview
│   │   ├── urls.py
│   │   ├── migrations/0001_initial.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_parsers.py
│   │       ├── test_models.py
│   │       └── test_views.py
│   ├── batch/                         NEW APP
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py                  BatchJob, BatchCallItem
│   │   ├── csv_validator.py           CSV header validation
│   │   ├── forms.py                   BatchUploadForm
│   │   ├── views.py                   list, create, detail
│   │   ├── urls.py
│   │   ├── tasks.py                   Celery: dispatch_batch_call
│   │   ├── services.py                Render prompt + POST to BOT_VOZ
│   │   ├── migrations/0001_initial.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_csv_validator.py
│   │       ├── test_services.py
│   │       ├── test_tasks.py
│   │       └── test_views.py
│   └── calls/                         EXTENDED
│       ├── services/                  NEW SUBPACKAGE
│       │   ├── __init__.py
│       │   ├── gemini_analysis.py     Post-call Gemini extraction
│       │   └── gcs_audio.py           Signed URL generation
│       ├── webhook.py                 NEW — receives BOT_VOZ callback
│       ├── tasks.py                   NEW — Celery analysis task
│       └── tests/
│           ├── test_webhook.py
│           ├── test_gemini_analysis.py
│           └── test_tasks.py
├── api/v1/
│   ├── batch.py                       NEW — REST endpoint for batch creation
│   └── webhook.py                     NEW — webhook receiver schema
└── templates/
    ├── scripts/
    │   ├── list.html                  NEW
    │   ├── form.html                  NEW
    │   └── preview.html               NEW
    ├── batch/
    │   ├── list.html                  NEW
    │   ├── create.html                NEW
    │   ├── detail.html                NEW
    │   └── partials/
    │       └── progress.html          NEW (HTMX polling)
    ├── calls/
    │   └── detail.html                MODIFIED — audio player, [[params]] card
    └── dashboard.html                  MODIFIED — new KPIs + [[params]] panel
```

**Files to delete:**

```
call-workspace/apps/processing/transcription.py        (AssemblyAI)
call-workspace/apps/processing/analysis.py             (OpenRouter)
call-workspace/apps/processing/ftp_client.py           (FTP)
call-workspace/apps/processing/tasks.py                (FTP polling)
call-workspace/apps/calls/views.py:upload              (manual upload view)
call-workspace/templates/calls/upload.html             (manual upload form)
call-workspace/apps/reviews/                           (whole app — out of scope)
call-workspace/apps/calls/models.py:Transcription      (replaced by Call.transcript JSON)
call-workspace/apps/calls/models.py:ComplianceAnalysis (replaced by CallAnalysis)
call-workspace/apps/campaigns/models.py:Agent          (no human agents in v1)
```

---

## Phase 1 — Foundation & Cleanup

### Task 1.1: Update requirements.txt

**Files:**
- Modify: `call-workspace/requirements.txt`

- [ ] **Step 1: Replace requirements with the new dependency set**

Replace entire `call-workspace/requirements.txt`:

```
Django>=5.1,<5.2
django-ninja>=1.3,<2.0
mssql-django>=1.5
pyodbc>=5.1
celery>=5.4
redis>=5.0
gunicorn>=22.0
whitenoise>=6.7
python-dotenv>=1.0
httpx>=0.27
google-cloud-aiplatform>=1.60
google-cloud-storage>=2.18
google-auth>=2.34
pandas>=2.2
pydantic>=2.8
```

Removed: `psycopg2-binary`, `paramiko`, `assemblyai`. Replaced with mssql-django, google-cloud-aiplatform, google-cloud-storage, pandas.

- [ ] **Step 2: Commit**

```bash
git add call-workspace/requirements.txt
git commit -m "chore(deps): swap to SQL Server + Vertex AI + GCS dependencies"
```

---

### Task 1.2: Configure SQL Server and Vertex AI in Django settings

**Files:**
- Modify: `call-workspace/config/settings/base.py`
- Modify: `call-workspace/.env.example`

- [ ] **Step 1: Update DATABASES block in `base.py`**

Replace the existing `DATABASES` config with:

```python
DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.getenv("MSSQL_DB", "callworkspace"),
        "USER": os.getenv("MSSQL_USER", "sa"),
        "PASSWORD": os.getenv("MSSQL_PASSWORD", ""),
        "HOST": os.getenv("MSSQL_HOST", "localhost"),
        "PORT": os.getenv("MSSQL_PORT", "1433"),
        "OPTIONS": {
            "driver": os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"),
            "extra_params": "TrustServerCertificate=yes;",
        },
    }
}
```

- [ ] **Step 2: Add GCP / Vertex AI settings at end of `base.py`**

```python
# --- GCP / Vertex AI ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
GCS_AUDIO_BUCKET = os.getenv("GCS_AUDIO_BUCKET", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# --- BOT_VOZ ---
BOT_VOZ_BASE_URL = os.getenv("BOT_VOZ_BASE_URL", "http://localhost:8080")
BOT_VOZ_TIMEOUT_SECONDS = int(os.getenv("BOT_VOZ_TIMEOUT_SECONDS", "30"))
WEBHOOK_PUBLIC_URL = os.getenv("WEBHOOK_PUBLIC_URL", "http://localhost:8000")
```

- [ ] **Step 3: Update `.env.example`**

Replace the entire file:

```
SECRET_KEY=change-me
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1

# SQL Server
MSSQL_DB=callworkspace
MSSQL_USER=sa
MSSQL_PASSWORD=YourStrong!Pass
MSSQL_HOST=localhost
MSSQL_PORT=1433
MSSQL_DRIVER=ODBC Driver 18 for SQL Server

# Redis / Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# GCP
GCP_PROJECT_ID=botvozcrmintouch
GCP_REGION=us-central1
GCS_AUDIO_BUCKET=botvoz-call-audio
GEMINI_MODEL=gemini-2.5-pro
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# BOT_VOZ
BOT_VOZ_BASE_URL=http://localhost:8080
BOT_VOZ_TIMEOUT_SECONDS=30
WEBHOOK_PUBLIC_URL=http://localhost:8000
```

- [ ] **Step 4: Verify Django can load settings**

Run from `call-workspace/`:
```bash
python -c "from django.conf import settings; import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup(); print(settings.DATABASES['default']['ENGINE'])"
```
Expected output: `mssql`

- [ ] **Step 5: Commit**

```bash
git add call-workspace/config/settings/base.py call-workspace/.env.example
git commit -m "feat(config): switch DB to SQL Server, add Vertex AI + BOT_VOZ settings"
```

---

### Task 1.3: Remove obsolete code (AssemblyAI, OpenRouter, FTP, reviews app, manual upload)

**Files:**
- Delete: `call-workspace/apps/processing/transcription.py`
- Delete: `call-workspace/apps/processing/analysis.py`
- Delete: `call-workspace/apps/processing/ftp_client.py`
- Delete: `call-workspace/apps/processing/tasks.py`
- Delete: `call-workspace/apps/reviews/` (entire folder)
- Delete: `call-workspace/templates/calls/upload.html`
- Delete: `call-workspace/templates/reviews/` (entire folder)
- Delete: `call-workspace/api/v1/reviews.py`
- Modify: `call-workspace/config/settings/base.py` (remove `apps.reviews` from INSTALLED_APPS, remove CELERY_BEAT_SCHEDULE FTP entry)
- Modify: `call-workspace/config/urls.py` (remove reviews routes)
- Modify: `call-workspace/api/v1/router.py` (remove reviews router)
- Modify: `call-workspace/apps/calls/views.py` (remove `upload` view)
- Modify: `call-workspace/apps/calls/urls.py` (remove `upload` URL)

- [ ] **Step 1: Delete obsolete files**

```bash
cd call-workspace
rm apps/processing/transcription.py
rm apps/processing/analysis.py
rm apps/processing/ftp_client.py
rm apps/processing/tasks.py
rm -rf apps/reviews
rm templates/calls/upload.html
rm -rf templates/reviews
rm api/v1/reviews.py
```

- [ ] **Step 2: Remove `apps.reviews` from INSTALLED_APPS in `base.py`**

In `call-workspace/config/settings/base.py`, locate the `INSTALLED_APPS` list and remove the line `"apps.reviews",`.

- [ ] **Step 3: Remove `CELERY_BEAT_SCHEDULE` FTP entry from `base.py`**

In `call-workspace/config/settings/base.py`, delete the `CELERY_BEAT_SCHEDULE` block (the one referencing `poll_ftp_task`). If the block has no other entries, delete the whole block.

- [ ] **Step 4: Remove reviews from `config/urls.py`**

In `call-workspace/config/urls.py`, find the line including reviews URLs:
```python
path("reviews/", include("apps.reviews.urls")),
```
Delete it.

- [ ] **Step 5: Remove reviews router from `api/v1/router.py`**

In `call-workspace/api/v1/router.py`, remove the import and `add_router` call referencing reviews.

- [ ] **Step 6: Remove upload view + URL in calls app**

In `call-workspace/apps/calls/views.py`, delete the function `upload` (and any helpers used only by it).
In `call-workspace/apps/calls/urls.py`, remove the URL pattern with `name="upload"` or path `"nueva/"`.

- [ ] **Step 7: Verify Django still imports**

```bash
cd call-workspace
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: remove AssemblyAI, OpenRouter, FTP, reviews, manual upload"
```

---

### Task 1.4: Reset migrations and prepare clean schema

**Files:**
- Delete all migration files except `__init__.py` in each migrations directory

- [ ] **Step 1: Delete existing migration files**

```bash
cd call-workspace
find apps -path "*/migrations/*.py" ! -name "__init__.py" -delete
```

Expected: removes `0001_initial.py` from `accounts`, `calls`, `campaigns` (reviews directory already deleted).

- [ ] **Step 2: Verify Django still imports**

```bash
python manage.py check
```
Expected: `System check identified no issues`.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore(db): reset migrations before SQL Server schema rebuild"
```

---

## Phase 2 — Scripts App

### Task 2.1: Create `scripts` Django app

**Files:**
- Create: `call-workspace/apps/scripts/__init__.py` (empty)
- Create: `call-workspace/apps/scripts/apps.py`
- Create: `call-workspace/apps/scripts/admin.py`
- Create: `call-workspace/apps/scripts/migrations/__init__.py` (empty)
- Modify: `call-workspace/config/settings/base.py` (add `apps.scripts` to INSTALLED_APPS)

- [ ] **Step 1: Create the app skeleton**

`call-workspace/apps/scripts/apps.py`:
```python
from django.apps import AppConfig


class ScriptsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scripts"
    verbose_name = "Bot Scripts"
```

`call-workspace/apps/scripts/admin.py`:
```python
from django.contrib import admin

from .models import Script


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ("name", "input_params", "output_params", "updated_at")
    search_fields = ("name",)
```

`call-workspace/apps/scripts/__init__.py`: empty file.
`call-workspace/apps/scripts/migrations/__init__.py`: empty file.

- [ ] **Step 2: Register app in settings**

In `call-workspace/config/settings/base.py`, add `"apps.scripts",` to `INSTALLED_APPS`.

- [ ] **Step 3: Commit (no test yet — model comes next)**

```bash
git add call-workspace/apps/scripts call-workspace/config/settings/base.py
git commit -m "feat(scripts): scaffold scripts app"
```

---

### Task 2.2: Write script template parser (TDD)

**Files:**
- Create: `call-workspace/apps/scripts/tests/__init__.py` (empty)
- Create: `call-workspace/apps/scripts/tests/test_parsers.py`
- Create: `call-workspace/apps/scripts/parsers.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/scripts/tests/test_parsers.py`:
```python
import pytest

from apps.scripts.parsers import parse_template, render_template


class TestParseTemplate:
    def test_extracts_input_params_simple(self):
        text = "Hola {{nombre}}, lo llamo por {{fecha}}."
        result = parse_template(text)
        assert result.input_params == ["nombre", "fecha"]
        assert result.output_params == []

    def test_extracts_output_params(self):
        text = "Anota [[confirmacion]] y [[nueva_fecha]] si aplica."
        result = parse_template(text)
        assert result.input_params == []
        assert result.output_params == ["confirmacion", "nueva_fecha"]

    def test_mixed_params(self):
        text = "Hola {{nombre}}. Anota [[confirmacion]]. Visita el {{fecha}}."
        result = parse_template(text)
        assert result.input_params == ["nombre", "fecha"]
        assert result.output_params == ["confirmacion"]

    def test_deduplicates_params(self):
        text = "{{nombre}}... {{nombre}} otra vez. [[ok]] [[ok]]."
        result = parse_template(text)
        assert result.input_params == ["nombre"]
        assert result.output_params == ["ok"]

    def test_ignores_single_braces(self):
        text = "Esto {no} es {param}. Pero {{si}} lo es."
        result = parse_template(text)
        assert result.input_params == ["si"]


class TestRenderTemplate:
    def test_replaces_input_params(self):
        text = "Hola {{nombre}}, hoy es {{fecha}}."
        result = render_template(text, {"nombre": "Juan", "fecha": "13 mayo"})
        assert result == "Hola Juan, hoy es 13 mayo."

    def test_leaves_output_params_untouched(self):
        text = "Hola {{nombre}}. Anota [[confirmacion]]."
        result = render_template(text, {"nombre": "Juan"})
        assert result == "Hola Juan. Anota [[confirmacion]]."

    def test_missing_param_raises(self):
        text = "Hola {{nombre}}, hoy es {{fecha}}."
        with pytest.raises(KeyError, match="fecha"):
            render_template(text, {"nombre": "Juan"})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd call-workspace
pytest apps/scripts/tests/test_parsers.py -v
```
Expected: FAIL with `ImportError: cannot import name 'parse_template'`.

- [ ] **Step 3: Implement the parser**

`call-workspace/apps/scripts/parsers.py`:
```python
"""Pure-function parser for script templates with {{input}} and [[output]] syntax."""

import re
from dataclasses import dataclass
from typing import Mapping

INPUT_PATTERN = re.compile(r"\{\{(\w+)\}\}")
OUTPUT_PATTERN = re.compile(r"\[\[(\w+)\]\]")


@dataclass(frozen=True)
class ParsedTemplate:
    input_params: list[str]
    output_params: list[str]


def parse_template(text: str) -> ParsedTemplate:
    """Extract {{input}} and [[output]] parameter names, deduplicated, in order of first appearance."""
    return ParsedTemplate(
        input_params=_unique_in_order(INPUT_PATTERN.findall(text)),
        output_params=_unique_in_order(OUTPUT_PATTERN.findall(text)),
    )


def render_template(text: str, values: Mapping[str, str]) -> str:
    """Replace {{params}} with values; leave [[params]] untouched. Raises KeyError if a value is missing."""
    parsed = parse_template(text)
    missing = [p for p in parsed.input_params if p not in values]
    if missing:
        raise KeyError(f"Missing values for: {', '.join(missing)}")

    def substitute(match: re.Match) -> str:
        return str(values[match.group(1)])

    return INPUT_PATTERN.sub(substitute, text)


def _unique_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest apps/scripts/tests/test_parsers.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/scripts/parsers.py call-workspace/apps/scripts/tests
git commit -m "feat(scripts): add {{input}}/[[output]] template parser"
```

---

### Task 2.3: Write Script model + auto-parse on save

**Files:**
- Create: `call-workspace/apps/scripts/models.py`
- Create: `call-workspace/apps/scripts/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/scripts/tests/test_models.py`:
```python
import pytest

from apps.scripts.models import Script


@pytest.mark.django_db
class TestScriptModel:
    def test_parses_input_and_output_params_on_save(self):
        s = Script.objects.create(
            name="confirm-visit",
            prompt_template="Hola {{nombre}}, confirma [[asistencia]] para el {{fecha}}.",
            greeting="Hola {{nombre}}",
        )
        s.refresh_from_db()
        assert s.input_params == ["nombre", "fecha"]
        assert s.output_params == ["asistencia"]

    def test_reparses_on_update(self):
        s = Script.objects.create(
            name="x",
            prompt_template="{{a}} [[b]]",
            greeting="hola",
        )
        s.prompt_template = "{{c}} [[d]]"
        s.save()
        s.refresh_from_db()
        assert s.input_params == ["c"]
        assert s.output_params == ["d"]

    def test_str_returns_name(self):
        s = Script(name="my-script", prompt_template="x", greeting="y")
        assert str(s) == "my-script"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd call-workspace
pytest apps/scripts/tests/test_models.py -v
```
Expected: FAIL with `ImportError: cannot import name 'Script'`.

- [ ] **Step 3: Implement the model**

`call-workspace/apps/scripts/models.py`:
```python
from django.db import models

from .parsers import parse_template


class Script(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    prompt_template = models.TextField()
    greeting = models.CharField(max_length=500)
    input_params = models.JSONField(default=list, blank=True)
    output_params = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        parsed = parse_template(self.prompt_template)
        self.input_params = parsed.input_params
        self.output_params = parsed.output_params
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Generate migration**

```bash
cd call-workspace
python manage.py makemigrations scripts
```
Expected: creates `apps/scripts/migrations/0001_initial.py`.

- [ ] **Step 5: Run tests (uses in-memory sqlite for tests via Django default)**

Add `call-workspace/pytest.ini` (if missing):
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.dev
python_files = test_*.py
```

Run:
```bash
pytest apps/scripts/tests/test_models.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add call-workspace/apps/scripts/models.py call-workspace/apps/scripts/migrations call-workspace/apps/scripts/tests/test_models.py call-workspace/pytest.ini
git commit -m "feat(scripts): Script model with auto-parsed input/output params"
```

---

### Task 2.4: Build Script CRUD views + templates

**Files:**
- Create: `call-workspace/apps/scripts/forms.py`
- Create: `call-workspace/apps/scripts/views.py`
- Create: `call-workspace/apps/scripts/urls.py`
- Create: `call-workspace/templates/scripts/list.html`
- Create: `call-workspace/templates/scripts/form.html`
- Create: `call-workspace/templates/scripts/preview.html`
- Create: `call-workspace/apps/scripts/tests/test_views.py`
- Modify: `call-workspace/config/urls.py` (include scripts URLs)
- Modify: `call-workspace/templates/base.html` (add nav link)

- [ ] **Step 1: Write a smoke test for the views**

`call-workspace/apps/scripts/tests/test_views.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.scripts.models import Script

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="u", password="p")


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_list_view_renders(client_logged_in):
    Script.objects.create(name="s1", prompt_template="x", greeting="g")
    response = client_logged_in.get(reverse("scripts:list"))
    assert response.status_code == 200
    assert b"s1" in response.content


@pytest.mark.django_db
def test_create_view_saves_and_parses(client_logged_in):
    response = client_logged_in.post(
        reverse("scripts:create"),
        {
            "name": "new-script",
            "description": "",
            "prompt_template": "Hola {{nombre}}, anota [[ok]].",
            "greeting": "Hola",
        },
    )
    assert response.status_code == 302
    script = Script.objects.get(name="new-script")
    assert script.input_params == ["nombre"]
    assert script.output_params == ["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd call-workspace
pytest apps/scripts/tests/test_views.py -v
```
Expected: FAIL with `Reverse for 'scripts:list' not found`.

- [ ] **Step 3: Implement the form**

`call-workspace/apps/scripts/forms.py`:
```python
from django import forms

from .models import Script


class ScriptForm(forms.ModelForm):
    class Meta:
        model = Script
        fields = ["name", "description", "prompt_template", "greeting"]
        widgets = {
            "prompt_template": forms.Textarea(attrs={"rows": 12, "class": "w-full font-mono text-sm"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "w-full"}),
            "name": forms.TextInput(attrs={"class": "w-full"}),
            "greeting": forms.TextInput(attrs={"class": "w-full"}),
        }
```

- [ ] **Step 4: Implement the views**

`call-workspace/apps/scripts/views.py`:
```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ScriptForm
from .models import Script
from .parsers import parse_template, render_template


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
```

- [ ] **Step 5: Implement URLs**

`call-workspace/apps/scripts/urls.py`:
```python
from django.urls import path

from . import views

app_name = "scripts"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nuevo/", views.create_view, name="create"),
    path("<int:pk>/editar/", views.edit_view, name="edit"),
    path("<int:pk>/preview/", views.preview_view, name="preview"),
]
```

In `call-workspace/config/urls.py`, add:
```python
path("scripts/", include("apps.scripts.urls")),
```

- [ ] **Step 6: Implement templates**

`call-workspace/templates/scripts/list.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6">
  <div class="flex justify-between mb-4">
    <h1 class="text-2xl font-bold">Scripts</h1>
    <a href="{% url 'scripts:create' %}" class="bg-blue-600 text-white px-4 py-2 rounded">Nuevo script</a>
  </div>
  <table class="w-full bg-white shadow rounded">
    <thead class="bg-gray-100">
      <tr>
        <th class="text-left p-3">Nombre</th>
        <th class="text-left p-3">Inputs {{}}</th>
        <th class="text-left p-3">Outputs [[]]</th>
        <th class="text-left p-3">Actualizado</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for s in scripts %}
      <tr class="border-t">
        <td class="p-3 font-medium">{{ s.name }}</td>
        <td class="p-3 text-sm text-gray-600">{{ s.input_params|join:", " }}</td>
        <td class="p-3 text-sm text-gray-600">{{ s.output_params|join:", " }}</td>
        <td class="p-3 text-sm text-gray-500">{{ s.updated_at|date:"Y-m-d H:i" }}</td>
        <td class="p-3">
          <a href="{% url 'scripts:edit' s.pk %}" class="text-blue-600">Editar</a> ·
          <a href="{% url 'scripts:preview' s.pk %}" class="text-blue-600">Preview</a>
        </td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="p-6 text-center text-gray-500">No hay scripts aún.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`call-workspace/templates/scripts/form.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-3xl">
  <h1 class="text-2xl font-bold mb-4">{{ title }}</h1>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="block font-medium">Nombre</label>
      {{ form.name }}
    </div>
    <div>
      <label class="block font-medium">Descripción</label>
      {{ form.description }}
    </div>
    <div>
      <label class="block font-medium">Saludo inicial</label>
      {{ form.greeting }}
    </div>
    <div>
      <label class="block font-medium">Prompt / instrucciones para el bot</label>
      <div class="text-xs text-gray-500 mb-1">
        Usa <code>{{ "{{" }}param{{ "}}" }}</code> para datos que pases por código y
        <code>[[param]]</code> para datos que el bot debe recolectar.
      </div>
      {{ form.prompt_template }}
    </div>
    {% if form.errors %}<div class="text-red-600">{{ form.errors }}</div>{% endif %}
    <button class="bg-blue-600 text-white px-4 py-2 rounded">Guardar</button>
    <a href="{% url 'scripts:list' %}" class="px-4 py-2">Cancelar</a>
  </form>

  {% if script %}
  <div class="mt-6 bg-gray-50 p-4 rounded text-sm">
    <div><strong>Inputs detectados:</strong> {{ script.input_params|join:", "|default:"—" }}</div>
    <div><strong>Outputs detectados:</strong> {{ script.output_params|join:", "|default:"—" }}</div>
  </div>
  {% endif %}
</div>
{% endblock %}
```

`call-workspace/templates/scripts/preview.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-3xl">
  <h1 class="text-2xl font-bold mb-4">Preview: {{ script.name }}</h1>
  <p class="text-sm text-gray-500 mb-2">Los <code>{{ "{{" }}param{{ "}}" }}</code> se reemplazaron con placeholders <code>&lt;param&gt;</code> de ejemplo.</p>
  <pre class="bg-gray-100 p-4 rounded whitespace-pre-wrap text-sm">{{ rendered }}</pre>
  <a href="{% url 'scripts:list' %}" class="text-blue-600 mt-4 inline-block">← Volver</a>
</div>
{% endblock %}
```

- [ ] **Step 7: Add nav link in `base.html`**

In `call-workspace/templates/base.html`, find the nav bar and add:
```html
<a href="{% url 'scripts:list' %}" class="px-3 py-2 hover:bg-gray-100">Scripts</a>
```

- [ ] **Step 8: Run tests**

```bash
pytest apps/scripts/tests/test_views.py -v
```
Expected: 2 passed.

- [ ] **Step 9: Commit**

```bash
git add call-workspace/apps/scripts call-workspace/templates/scripts call-workspace/config/urls.py call-workspace/templates/base.html
git commit -m "feat(scripts): CRUD views, forms, and templates"
```

---

## Phase 3 — Campaign Update

### Task 3.1: Update Campaign model (add Script FK, remove FTP fields and Agent)

**Files:**
- Modify: `call-workspace/apps/campaigns/models.py`
- Modify: `call-workspace/apps/campaigns/forms.py`
- Modify: `call-workspace/apps/campaigns/views.py`
- Modify: `call-workspace/apps/campaigns/admin.py`
- Modify: `call-workspace/apps/campaigns/urls.py`
- Modify: `call-workspace/templates/campaigns/form.html`
- Modify: `call-workspace/templates/campaigns/list.html`
- Delete: `call-workspace/templates/campaigns/agents/`
- Delete: any agent-related templates/views

- [ ] **Step 1: Replace `apps/campaigns/models.py`**

```python
from django.db import models


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    script = models.ForeignKey(
        "scripts.Script",
        on_delete=models.PROTECT,
        related_name="campaigns",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name
```

- [ ] **Step 2: Update `forms.py`, `views.py`, and `admin.py`**

`call-workspace/apps/campaigns/forms.py`:
```python
from django import forms

from .models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "description", "script", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2, "class": "w-full"}),
            "name": forms.TextInput(attrs={"class": "w-full"}),
        }
```

`call-workspace/apps/campaigns/admin.py`:
```python
from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "script", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
```

`call-workspace/apps/campaigns/views.py` — replace entire contents:
```python
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
```

`call-workspace/apps/campaigns/urls.py`:
```python
from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nueva/", views.create_view, name="create"),
    path("<int:pk>/editar/", views.edit_view, name="edit"),
]
```

- [ ] **Step 3: Delete agent-related templates**

```bash
cd call-workspace
rm -rf templates/campaigns/agents
rm templates/campaigns/partials/status_badge.html 2>/dev/null || true
```

- [ ] **Step 4: Replace `templates/campaigns/list.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="p-6">
  <div class="flex justify-between mb-4">
    <h1 class="text-2xl font-bold">Campañas</h1>
    <a href="{% url 'campaigns:create' %}" class="bg-blue-600 text-white px-4 py-2 rounded">Nueva campaña</a>
  </div>
  <table class="w-full bg-white shadow rounded">
    <thead class="bg-gray-100">
      <tr>
        <th class="text-left p-3">Nombre</th>
        <th class="text-left p-3">Script</th>
        <th class="text-left p-3">Activa</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for c in campaigns %}
      <tr class="border-t">
        <td class="p-3 font-medium">{{ c.name }}</td>
        <td class="p-3">{{ c.script.name|default:"—" }}</td>
        <td class="p-3">{% if c.is_active %}<span class="text-green-600">●</span>{% else %}<span class="text-gray-400">●</span>{% endif %}</td>
        <td class="p-3"><a href="{% url 'campaigns:edit' c.pk %}" class="text-blue-600">Editar</a></td>
      </tr>
      {% empty %}
      <tr><td colspan="4" class="p-6 text-center text-gray-500">No hay campañas.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

- [ ] **Step 5: Replace `templates/campaigns/form.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-2xl">
  <h1 class="text-2xl font-bold mb-4">{{ title }}</h1>
  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div><label class="block font-medium">Nombre</label>{{ form.name }}</div>
    <div><label class="block font-medium">Descripción</label>{{ form.description }}</div>
    <div><label class="block font-medium">Script</label>{{ form.script }}</div>
    <div class="flex items-center gap-2">{{ form.is_active }}<label>Activa</label></div>
    {% if form.errors %}<div class="text-red-600">{{ form.errors }}</div>{% endif %}
    <button class="bg-blue-600 text-white px-4 py-2 rounded">Guardar</button>
    <a href="{% url 'campaigns:list' %}" class="px-4 py-2">Cancelar</a>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: Generate migration and verify**

```bash
cd call-workspace
python manage.py makemigrations campaigns
python manage.py check
```
Expected: creates `apps/campaigns/migrations/0001_initial.py`, check passes.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(campaigns): link to Script, remove Agent + FTP fields"
```

---

## Phase 4 — Call Model Refactor

### Task 4.1: Rewrite Call models for new schema

**Files:**
- Replace: `call-workspace/apps/calls/models.py`
- Modify: `call-workspace/apps/calls/admin.py`

- [ ] **Step 1: Replace `apps/calls/models.py`**

```python
import uuid

from django.db import models


class Call(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("calling", "Calling"),
        ("analyzing", "Analyzing"),
        ("done", "Done"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_item = models.ForeignKey(
        "batch.BatchCallItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calls",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.PROTECT,
        related_name="calls",
    )
    phone_number = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transcript = models.JSONField(default=list, blank=True)
    audio_gcs_url = models.CharField(max_length=500, blank=True, default="")
    duration_seconds = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    bot_call_id = models.CharField(max_length=100, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["campaign", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Call {self.id} → {self.phone_number}"


class CallAnalysis(models.Model):
    call = models.OneToOneField(Call, on_delete=models.CASCADE, related_name="analysis")
    output_data = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True, default="")
    compliance_score = models.IntegerField(null=True, blank=True)
    llm_model = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
```

- [ ] **Step 2: Replace `apps/calls/admin.py`**

```python
from django.contrib import admin

from .models import Call, CallAnalysis


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("id", "phone_number", "campaign", "status", "created_at")
    list_filter = ("status", "campaign")
    search_fields = ("phone_number", "id")
    readonly_fields = ("id", "created_at", "started_at", "ended_at")


@admin.register(CallAnalysis)
class CallAnalysisAdmin(admin.ModelAdmin):
    list_display = ("call", "compliance_score", "llm_model", "created_at")
```

- [ ] **Step 3: Note — migration is deferred**

The migration cannot be generated until the `batch` app (referenced by the `batch_item` FK) exists. We'll generate migrations in a later task after `batch` is scaffolded.

- [ ] **Step 4: Commit (no test yet — model is referenced by webhook/analysis tasks built later)**

```bash
git add call-workspace/apps/calls/models.py call-workspace/apps/calls/admin.py
git commit -m "feat(calls): rewrite Call model + add CallAnalysis"
```

---

### Task 4.2: Clean up obsolete calls views and templates

**Files:**
- Replace: `call-workspace/apps/calls/views.py`
- Replace: `call-workspace/apps/calls/urls.py`
- Delete: `call-workspace/templates/calls/list.html` contents will be rewritten in later task
- Delete: `call-workspace/templates/calls/detail.html` contents will be rewritten
- Delete: `call-workspace/templates/calls/partials/agent_options.html`
- Delete: `call-workspace/templates/calls/partials/rows.html` (will recreate later)

- [ ] **Step 1: Replace `apps/calls/views.py` with minimal stubs (will be expanded later)**

```python
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
    """Placeholder — final dashboard built in Task 9.1."""
    return render(request, "dashboard.html", {})
```

- [ ] **Step 2: Replace `apps/calls/urls.py`**

```python
from django.urls import path

from . import views

app_name = "calls"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("<uuid:pk>/", views.detail_view, name="detail"),
]
```

- [ ] **Step 3: Delete obsolete partials**

```bash
cd call-workspace
rm -f templates/calls/partials/agent_options.html
rm -f templates/calls/partials/rows.html
```

- [ ] **Step 4: Stub `templates/calls/list.html` and `templates/calls/detail.html`** (will be polished in Task 9.3)

`call-workspace/templates/calls/list.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6">
  <h1 class="text-2xl font-bold mb-4">Llamadas</h1>
  <table class="w-full bg-white shadow rounded text-sm">
    <thead class="bg-gray-100">
      <tr>
        <th class="text-left p-2">Teléfono</th>
        <th class="text-left p-2">Campaña</th>
        <th class="text-left p-2">Estado</th>
        <th class="text-left p-2">Creada</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for c in calls %}
      <tr class="border-t">
        <td class="p-2">{{ c.phone_number }}</td>
        <td class="p-2">{{ c.campaign.name }}</td>
        <td class="p-2">{{ c.get_status_display }}</td>
        <td class="p-2">{{ c.created_at|date:"Y-m-d H:i" }}</td>
        <td class="p-2"><a href="{% url 'calls:detail' c.pk %}" class="text-blue-600">Ver</a></td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="p-6 text-center text-gray-500">No hay llamadas.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`call-workspace/templates/calls/detail.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-4xl">
  <h1 class="text-2xl font-bold mb-4">Llamada {{ call.id }}</h1>
  <p>Teléfono: {{ call.phone_number }}</p>
  <p>Estado: {{ call.get_status_display }}</p>
  <p>Duración: {{ call.duration_seconds|default:"—" }}s</p>
  {% if call.analysis %}
    <h2 class="text-xl font-bold mt-6">Datos recolectados</h2>
    <pre class="bg-gray-100 p-3 rounded">{{ call.analysis.output_data }}</pre>
    <h2 class="text-xl font-bold mt-6">Resumen</h2>
    <p>{{ call.analysis.summary }}</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Verify Django check**

```bash
python manage.py check
```
Expected: `System check identified no issues.`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(calls): simplify views + stub templates pending dashboard polish"
```

---

## Phase 5 — Batch App

### Task 5.1: Scaffold `batch` Django app

**Files:**
- Create: `call-workspace/apps/batch/__init__.py` (empty)
- Create: `call-workspace/apps/batch/apps.py`
- Create: `call-workspace/apps/batch/admin.py`
- Create: `call-workspace/apps/batch/migrations/__init__.py` (empty)
- Modify: `call-workspace/config/settings/base.py` (add `apps.batch` to INSTALLED_APPS)

- [ ] **Step 1: Create app skeleton**

`call-workspace/apps/batch/apps.py`:
```python
from django.apps import AppConfig


class BatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.batch"
    verbose_name = "Batch Calls"
```

`call-workspace/apps/batch/admin.py`:
```python
from django.contrib import admin

from .models import BatchCallItem, BatchJob


@admin.register(BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "source", "total_calls", "done_calls", "status", "created_at")
    list_filter = ("status", "source")


@admin.register(BatchCallItem)
class BatchCallItemAdmin(admin.ModelAdmin):
    list_display = ("id", "batch_job", "phone_number", "status")
    list_filter = ("status",)
```

`call-workspace/apps/batch/__init__.py`: empty
`call-workspace/apps/batch/migrations/__init__.py`: empty

In `call-workspace/config/settings/base.py`, add `"apps.batch",` to `INSTALLED_APPS`.

- [ ] **Step 2: Commit**

```bash
git add call-workspace/apps/batch call-workspace/config/settings/base.py
git commit -m "feat(batch): scaffold batch app"
```

---

### Task 5.2: BatchJob + BatchCallItem models

**Files:**
- Create: `call-workspace/apps/batch/models.py`

- [ ] **Step 1: Implement models**

```python
from django.db import models


class BatchJob(models.Model):
    SOURCE_CHOICES = [("csv", "CSV upload"), ("api", "REST API")]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.PROTECT, related_name="batch_jobs")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    total_calls = models.IntegerField(default=0)
    done_calls = models.IntegerField(default=0)
    failed_calls = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class BatchCallItem(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("calling", "Calling"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("retry", "Retry"),
    ]

    batch_job = models.ForeignKey(BatchJob, on_delete=models.CASCADE, related_name="items")
    phone_number = models.CharField(max_length=30)
    input_params = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, default="")
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["batch_job", "status"])]
```

- [ ] **Step 2: Generate migrations for batch + calls now that all FK targets exist**

```bash
cd call-workspace
python manage.py makemigrations batch calls
```
Expected: creates initial migrations.

- [ ] **Step 3: Verify check**

```bash
python manage.py check
```
Expected: `System check identified no issues.`

- [ ] **Step 4: Commit**

```bash
git add call-workspace/apps/batch/models.py call-workspace/apps/batch/migrations call-workspace/apps/calls/migrations
git commit -m "feat(batch): BatchJob + BatchCallItem models + migrations"
```

---

### Task 5.3: CSV validator (TDD)

**Files:**
- Create: `call-workspace/apps/batch/tests/__init__.py` (empty)
- Create: `call-workspace/apps/batch/tests/test_csv_validator.py`
- Create: `call-workspace/apps/batch/csv_validator.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/batch/tests/test_csv_validator.py`:
```python
import io

import pytest

from apps.batch.csv_validator import CsvValidationError, validate_and_parse_csv


def test_returns_rows_when_headers_match():
    csv_content = "phone_number,nombre,fecha\n+1,Juan,13/05\n+2,Maria,15/05\n"
    rows = validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])
    assert rows == [
        {"phone_number": "+1", "input_params": {"nombre": "Juan", "fecha": "13/05"}},
        {"phone_number": "+2", "input_params": {"nombre": "Maria", "fecha": "15/05"}},
    ]


def test_missing_phone_number_column_raises():
    csv_content = "nombre,fecha\nJuan,13/05\n"
    with pytest.raises(CsvValidationError, match="phone_number"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])


def test_missing_input_param_column_raises():
    csv_content = "phone_number,nombre\n+1,Juan\n"
    with pytest.raises(CsvValidationError, match="fecha"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre", "fecha"])


def test_empty_phone_number_row_raises():
    csv_content = "phone_number,nombre\n,Juan\n"
    with pytest.raises(CsvValidationError, match="empty"):
        validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre"])


def test_extra_columns_are_ignored():
    csv_content = "phone_number,nombre,extra\n+1,Juan,ignored\n"
    rows = validate_and_parse_csv(io.StringIO(csv_content), required_input_params=["nombre"])
    assert rows == [{"phone_number": "+1", "input_params": {"nombre": "Juan"}}]
```

- [ ] **Step 2: Run test (verify fail)**

```bash
cd call-workspace
pytest apps/batch/tests/test_csv_validator.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement the validator**

`call-workspace/apps/batch/csv_validator.py`:
```python
"""CSV parsing and validation for batch call uploads."""

import csv
from typing import IO


class CsvValidationError(ValueError):
    pass


def validate_and_parse_csv(file: IO[str], required_input_params: list[str]) -> list[dict]:
    reader = csv.DictReader(file)
    headers = reader.fieldnames or []

    if "phone_number" not in headers:
        raise CsvValidationError("CSV must include a 'phone_number' column.")

    missing = [p for p in required_input_params if p not in headers]
    if missing:
        raise CsvValidationError(f"CSV is missing required columns: {', '.join(missing)}")

    rows: list[dict] = []
    for idx, row in enumerate(reader, start=2):  # 2 because header is row 1
        phone = (row.get("phone_number") or "").strip()
        if not phone:
            raise CsvValidationError(f"Row {idx}: phone_number is empty.")
        input_params = {p: (row.get(p) or "").strip() for p in required_input_params}
        rows.append({"phone_number": phone, "input_params": input_params})

    return rows
```

- [ ] **Step 4: Run test (verify pass)**

```bash
pytest apps/batch/tests/test_csv_validator.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/batch/csv_validator.py call-workspace/apps/batch/tests
git commit -m "feat(batch): CSV validator with header + row checks"
```

---

### Task 5.4: BOT_VOZ dispatch service (TDD with mocked httpx)

**Files:**
- Create: `call-workspace/apps/batch/services.py`
- Create: `call-workspace/apps/batch/tests/test_services.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/batch/tests/test_services.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from apps.batch.services import BotVozDispatchError, build_call_payload, dispatch_call


def test_build_call_payload_renders_prompt_and_appends_output_instructions():
    script = MagicMock()
    script.prompt_template = "Hola {{nombre}}. Anota [[ok]]."
    script.greeting = "Hola {{nombre}}"
    script.output_params = ["ok"]

    payload = build_call_payload(
        call_id="abc-123",
        phone_number="+56912345678",
        script=script,
        input_params={"nombre": "Juan"},
        webhook_url="http://django/api/v1/calls/webhook/",
    )

    assert payload["call_id"] == "abc-123"
    assert payload["phone_number"] == "+56912345678"
    assert "Juan" in payload["rendered_prompt"]
    assert "[[ok]]" not in payload["rendered_prompt"]
    assert payload["greeting"] == "Hola Juan"
    assert payload["output_params"] == ["ok"]
    assert payload["webhook_url"] == "http://django/api/v1/calls/webhook/"


@patch("apps.batch.services.httpx.post")
def test_dispatch_call_posts_to_bot_voz(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"bot_call_id": "bot-xyz", "status": "initiated"},
    )
    result = dispatch_call(base_url="http://botvoz", payload={"call_id": "a"}, timeout=30)
    assert result == {"bot_call_id": "bot-xyz", "status": "initiated"}
    mock_post.assert_called_once_with(
        "http://botvoz/calls/initiate", json={"call_id": "a"}, timeout=30
    )


@patch("apps.batch.services.httpx.post")
def test_dispatch_call_raises_on_non_200(mock_post):
    mock_post.return_value = MagicMock(status_code=500, text="Boom")
    with pytest.raises(BotVozDispatchError, match="500"):
        dispatch_call(base_url="http://botvoz", payload={}, timeout=30)
```

- [ ] **Step 2: Run test (verify fail)**

```bash
cd call-workspace
pytest apps/batch/tests/test_services.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement the service**

`call-workspace/apps/batch/services.py`:
```python
"""Translate a BatchCallItem into a payload BOT_VOZ understands, and dispatch it."""

from typing import Any

import httpx

from apps.scripts.parsers import render_template


class BotVozDispatchError(RuntimeError):
    pass


_OUTPUT_INSTRUCTION_TEMPLATE = (
    "\n\n[Instrucciones del sistema] Al final de la conversación debes haber "
    "intentado recolectar los siguientes datos del cliente: {fields}. "
    "Si no lograste obtener alguno, déjalo en null. Cuando el cliente "
    "mencione fechas relativas (\"mañana\", \"el jueves\"), calcula la fecha "
    "exacta y confírmala con el cliente antes de cerrar."
)


def build_call_payload(
    *,
    call_id: str,
    phone_number: str,
    script,
    input_params: dict[str, str],
    webhook_url: str,
) -> dict[str, Any]:
    rendered_prompt = render_template(script.prompt_template, input_params)
    rendered_greeting = render_template(script.greeting, input_params)
    if script.output_params:
        rendered_prompt += _OUTPUT_INSTRUCTION_TEMPLATE.format(
            fields=", ".join(script.output_params)
        )
    return {
        "call_id": call_id,
        "phone_number": phone_number,
        "rendered_prompt": rendered_prompt,
        "greeting": rendered_greeting,
        "output_params": list(script.output_params),
        "webhook_url": webhook_url,
    }


def dispatch_call(*, base_url: str, payload: dict, timeout: int) -> dict:
    response = httpx.post(f"{base_url.rstrip('/')}/calls/initiate", json=payload, timeout=timeout)
    if response.status_code != 200:
        raise BotVozDispatchError(
            f"BOT_VOZ returned {response.status_code}: {response.text}"
        )
    return response.json()
```

- [ ] **Step 4: Run test (verify pass)**

```bash
pytest apps/batch/tests/test_services.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/batch/services.py call-workspace/apps/batch/tests/test_services.py
git commit -m "feat(batch): dispatch service to POST calls to BOT_VOZ"
```

---

### Task 5.5: Celery task to dispatch calls one by one

**Files:**
- Create: `call-workspace/apps/batch/tasks.py`
- Create: `call-workspace/apps/batch/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/batch/tests/test_tasks.py`:
```python
from unittest.mock import patch

import pytest

from apps.batch.models import BatchCallItem, BatchJob
from apps.batch.tasks import process_batch_item
from apps.calls.models import Call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def script(db):
    return Script.objects.create(
        name="s",
        prompt_template="Hola {{nombre}}. Anota [[ok]].",
        greeting="Hola {{nombre}}",
    )


@pytest.fixture
def campaign(db, script):
    return Campaign.objects.create(name="c", script=script)


@pytest.fixture
def batch_job(db, campaign):
    return BatchJob.objects.create(campaign=campaign, source="api", total_calls=1, status="running")


@pytest.mark.django_db
@patch("apps.batch.tasks.dispatch_call")
def test_process_batch_item_creates_call_and_dispatches(mock_dispatch, batch_job):
    mock_dispatch.return_value = {"bot_call_id": "bot-1", "status": "initiated"}
    item = BatchCallItem.objects.create(
        batch_job=batch_job, phone_number="+1", input_params={"nombre": "Juan"}
    )

    process_batch_item(item.id)

    item.refresh_from_db()
    assert item.status == "calling"
    call = Call.objects.get(batch_item=item)
    assert call.status == "calling"
    assert call.bot_call_id == "bot-1"
    mock_dispatch.assert_called_once()


@pytest.mark.django_db
@patch("apps.batch.tasks.dispatch_call", side_effect=Exception("network"))
def test_process_batch_item_marks_retry_on_failure(mock_dispatch, batch_job):
    item = BatchCallItem.objects.create(
        batch_job=batch_job, phone_number="+1", input_params={"nombre": "Juan"}
    )
    with pytest.raises(Exception):
        process_batch_item(item.id)
    item.refresh_from_db()
    assert item.status == "retry"
    assert item.attempts == 1
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest apps/batch/tests/test_tasks.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement the task**

`call-workspace/apps/batch/tasks.py`:
```python
import uuid
from datetime import datetime, timezone

from celery import shared_task
from django.conf import settings

from apps.calls.models import Call

from .models import BatchCallItem
from .services import build_call_payload, dispatch_call


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_batch_item(self, item_id: int) -> None:
    item = BatchCallItem.objects.select_related("batch_job__campaign__script").get(pk=item_id)
    script = item.batch_job.campaign.script
    if script is None:
        item.status = "failed"
        item.error_message = "Campaign has no script."
        item.save(update_fields=["status", "error_message"])
        return

    call = Call.objects.create(
        id=uuid.uuid4(),
        batch_item=item,
        campaign=item.batch_job.campaign,
        phone_number=item.phone_number,
        status="calling",
        started_at=datetime.now(timezone.utc),
    )

    payload = build_call_payload(
        call_id=str(call.id),
        phone_number=item.phone_number,
        script=script,
        input_params=item.input_params,
        webhook_url=f"{settings.WEBHOOK_PUBLIC_URL}/api/v1/calls/webhook/",
    )

    item.attempts += 1
    item.called_at = datetime.now(timezone.utc)
    try:
        response = dispatch_call(
            base_url=settings.BOT_VOZ_BASE_URL,
            payload=payload,
            timeout=settings.BOT_VOZ_TIMEOUT_SECONDS,
        )
        call.bot_call_id = response.get("bot_call_id", "")
        call.save(update_fields=["bot_call_id"])
        item.status = "calling"
        item.save(update_fields=["status", "attempts", "called_at"])
    except Exception as exc:
        call.status = "error"
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message"])
        item.status = "retry"
        item.error_message = str(exc)
        item.save(update_fields=["status", "attempts", "called_at", "error_message"])
        raise
```

- [ ] **Step 4: Run test (verify pass)**

```bash
pytest apps/batch/tests/test_tasks.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/batch/tasks.py call-workspace/apps/batch/tests/test_tasks.py
git commit -m "feat(batch): Celery task to dispatch one call to BOT_VOZ"
```

---

### Task 5.6: Batch creation views + templates (CSV upload + list/detail)

**Files:**
- Create: `call-workspace/apps/batch/forms.py`
- Create: `call-workspace/apps/batch/views.py`
- Create: `call-workspace/apps/batch/urls.py`
- Create: `call-workspace/templates/batch/list.html`
- Create: `call-workspace/templates/batch/create.html`
- Create: `call-workspace/templates/batch/detail.html`
- Create: `call-workspace/templates/batch/partials/progress.html`
- Modify: `call-workspace/config/urls.py`
- Modify: `call-workspace/templates/base.html` (add nav link)

- [ ] **Step 1: Implement forms**

`call-workspace/apps/batch/forms.py`:
```python
from django import forms

from apps.campaigns.models import Campaign


class BatchUploadForm(forms.Form):
    campaign = forms.ModelChoiceField(queryset=Campaign.objects.filter(is_active=True))
    csv_file = forms.FileField(help_text="CSV con columnas phone_number + parámetros del script.")
```

- [ ] **Step 2: Implement views**

`call-workspace/apps/batch/views.py`:
```python
import io

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .csv_validator import CsvValidationError, validate_and_parse_csv
from .forms import BatchUploadForm
from .models import BatchCallItem, BatchJob
from .tasks import process_batch_item


@login_required
def list_view(request):
    jobs = BatchJob.objects.select_related("campaign").all()
    return render(request, "batch/list.html", {"jobs": jobs})


@login_required
def create_view(request):
    if request.method == "POST":
        form = BatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            campaign = form.cleaned_data["campaign"]
            script = campaign.script
            if script is None:
                form.add_error("campaign", "Esta campaña no tiene script asignado.")
                return render(request, "batch/create.html", {"form": form})

            file_content = form.cleaned_data["csv_file"].read().decode("utf-8")
            try:
                rows = validate_and_parse_csv(io.StringIO(file_content), script.input_params)
            except CsvValidationError as exc:
                form.add_error("csv_file", str(exc))
                return render(request, "batch/create.html", {"form": form})

            job = BatchJob.objects.create(
                campaign=campaign,
                source="csv",
                total_calls=len(rows),
                status="running",
            )
            items = [
                BatchCallItem(
                    batch_job=job,
                    phone_number=r["phone_number"],
                    input_params=r["input_params"],
                )
                for r in rows
            ]
            BatchCallItem.objects.bulk_create(items)

            for item in BatchCallItem.objects.filter(batch_job=job):
                process_batch_item.delay(item.id)

            return redirect("batch:detail", pk=job.id)
    else:
        form = BatchUploadForm()
    return render(request, "batch/create.html", {"form": form})


@login_required
def detail_view(request, pk: int):
    job = get_object_or_404(
        BatchJob.objects.select_related("campaign").prefetch_related("items"),
        pk=pk,
    )
    return render(request, "batch/detail.html", {"job": job})


@login_required
def progress_partial(request, pk: int):
    """HTMX endpoint — returns progress bar fragment."""
    job = get_object_or_404(BatchJob, pk=pk)
    pct = 0 if job.total_calls == 0 else int(100 * (job.done_calls + job.failed_calls) / job.total_calls)
    return render(request, "batch/partials/progress.html", {"job": job, "pct": pct})
```

- [ ] **Step 3: Implement URLs**

`call-workspace/apps/batch/urls.py`:
```python
from django.urls import path

from . import views

app_name = "batch"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("nuevo/", views.create_view, name="create"),
    path("<int:pk>/", views.detail_view, name="detail"),
    path("<int:pk>/progress/", views.progress_partial, name="progress"),
]
```

In `call-workspace/config/urls.py`, add:
```python
path("batch/", include("apps.batch.urls")),
```

- [ ] **Step 4: Implement templates**

`call-workspace/templates/batch/list.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6">
  <div class="flex justify-between mb-4">
    <h1 class="text-2xl font-bold">Lotes de llamadas</h1>
    <a href="{% url 'batch:create' %}" class="bg-blue-600 text-white px-4 py-2 rounded">Subir CSV</a>
  </div>
  <table class="w-full bg-white shadow rounded text-sm">
    <thead class="bg-gray-100">
      <tr>
        <th class="p-2 text-left">ID</th>
        <th class="p-2 text-left">Campaña</th>
        <th class="p-2 text-left">Origen</th>
        <th class="p-2 text-left">Estado</th>
        <th class="p-2 text-left">Progreso</th>
        <th class="p-2 text-left">Creado</th>
      </tr>
    </thead>
    <tbody>
      {% for j in jobs %}
      <tr class="border-t">
        <td class="p-2"><a href="{% url 'batch:detail' j.pk %}" class="text-blue-600">#{{ j.id }}</a></td>
        <td class="p-2">{{ j.campaign.name }}</td>
        <td class="p-2">{{ j.get_source_display }}</td>
        <td class="p-2">{{ j.get_status_display }}</td>
        <td class="p-2">{{ j.done_calls }}/{{ j.total_calls }}</td>
        <td class="p-2">{{ j.created_at|date:"Y-m-d H:i" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="6" class="p-6 text-center text-gray-500">No hay lotes.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`call-workspace/templates/batch/create.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-2xl">
  <h1 class="text-2xl font-bold mb-4">Nuevo lote por CSV</h1>
  <form method="post" enctype="multipart/form-data" class="space-y-4">
    {% csrf_token %}
    <div><label class="block font-medium">Campaña</label>{{ form.campaign }}</div>
    <div><label class="block font-medium">Archivo CSV</label>{{ form.csv_file }}</div>
    {% if form.errors %}<div class="text-red-600">{{ form.errors }}</div>{% endif %}
    <button class="bg-blue-600 text-white px-4 py-2 rounded">Encolar lote</button>
  </form>
  <p class="mt-4 text-sm text-gray-500">El CSV debe incluir las columnas <code>phone_number</code> más los parámetros <code>{{ "{{" }}param{{ "}}" }}</code> del script.</p>
</div>
{% endblock %}
```

`call-workspace/templates/batch/detail.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-5xl">
  <h1 class="text-2xl font-bold mb-2">Lote #{{ job.id }} — {{ job.campaign.name }}</h1>
  <div id="progress-wrap" hx-get="{% url 'batch:progress' job.pk %}" hx-trigger="load, every 3s" hx-swap="innerHTML">
    {% include "batch/partials/progress.html" with job=job pct=0 %}
  </div>
  <h2 class="text-xl font-bold mt-6 mb-2">Items</h2>
  <table class="w-full bg-white shadow rounded text-sm">
    <thead class="bg-gray-100">
      <tr>
        <th class="p-2 text-left">Teléfono</th>
        <th class="p-2 text-left">Estado</th>
        <th class="p-2 text-left">Input params</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {% for item in job.items.all %}
      <tr class="border-t">
        <td class="p-2">{{ item.phone_number }}</td>
        <td class="p-2">{{ item.get_status_display }}</td>
        <td class="p-2 text-xs"><pre>{{ item.input_params }}</pre></td>
        <td class="p-2">
          {% with item.calls.first as call %}
            {% if call %}<a href="{% url 'calls:detail' call.pk %}" class="text-blue-600">Ver llamada</a>{% endif %}
          {% endwith %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

`call-workspace/templates/batch/partials/progress.html`:
```html
<div class="bg-white p-4 rounded shadow">
  <div class="flex justify-between text-sm mb-1">
    <span>{{ job.done_calls }}/{{ job.total_calls }} completadas · {{ job.failed_calls }} fallidas</span>
    <span>{{ job.get_status_display }}</span>
  </div>
  <div class="w-full bg-gray-200 rounded h-3">
    <div class="bg-blue-600 h-3 rounded" style="width: {{ pct }}%"></div>
  </div>
</div>
```

- [ ] **Step 5: Add nav link in `base.html`**

```html
<a href="{% url 'batch:list' %}" class="px-3 py-2 hover:bg-gray-100">Lotes</a>
```

Also confirm `base.html` loads HTMX via CDN (it should already from call-workspace heritage). If not, add to the `<head>`:
```html
<script src="https://unpkg.com/htmx.org@1.9.12"></script>
```

- [ ] **Step 6: Verify**

```bash
python manage.py check
```
Expected: passes.

- [ ] **Step 7: Commit**

```bash
git add call-workspace/apps/batch call-workspace/templates/batch call-workspace/config/urls.py call-workspace/templates/base.html
git commit -m "feat(batch): CSV upload, list/detail views, HTMX progress"
```

---

### Task 5.7: REST API for batch creation

**Files:**
- Create: `call-workspace/api/v1/batch.py`
- Modify: `call-workspace/api/v1/router.py`
- Create: `call-workspace/api/v1/tests/__init__.py` (empty)
- Create: `call-workspace/api/v1/tests/test_batch_api.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/api/v1/tests/test_batch_api.py`:
```python
import pytest
from django.contrib.auth import get_user_model

from apps.campaigns.models import Campaign
from apps.scripts.models import Script

User = get_user_model()


@pytest.fixture
def authed_client(client, db):
    user = User.objects.create_user(username="u", password="p")
    client.force_login(user)
    return client


@pytest.fixture
def campaign(db):
    script = Script.objects.create(
        name="s",
        prompt_template="Hola {{nombre}}. [[ok]]",
        greeting="Hola {{nombre}}",
    )
    return Campaign.objects.create(name="c", script=script, is_active=True)


@pytest.mark.django_db
def test_create_batch_via_api(authed_client, campaign, mocker):
    mocker.patch("apps.batch.views.process_batch_item.delay")
    mocker.patch("api.v1.batch.process_batch_item.delay")

    response = authed_client.post(
        "/api/v1/batch/",
        data={
            "campaign_id": campaign.id,
            "calls": [
                {"phone_number": "+1", "input_params": {"nombre": "Juan"}},
                {"phone_number": "+2", "input_params": {"nombre": "Maria"}},
            ],
        },
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_calls"] == 2
    assert body["status"] == "pending"
    assert "batch_job_id" in body


@pytest.mark.django_db
def test_api_rejects_missing_input_param(authed_client, campaign):
    response = authed_client.post(
        "/api/v1/batch/",
        data={
            "campaign_id": campaign.id,
            "calls": [{"phone_number": "+1", "input_params": {}}],
        },
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "nombre" in response.json()["detail"]
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest call-workspace/api/v1/tests/test_batch_api.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement API**

`call-workspace/api/v1/batch.py`:
```python
from ninja import Router, Schema
from pydantic import Field

from apps.batch.models import BatchCallItem, BatchJob
from apps.batch.tasks import process_batch_item
from apps.campaigns.models import Campaign

router = Router()


class CallItem(Schema):
    phone_number: str = Field(..., max_length=30)
    input_params: dict


class BatchCreateIn(Schema):
    campaign_id: int
    calls: list[CallItem]


class BatchCreateOut(Schema):
    batch_job_id: int
    total_calls: int
    status: str


@router.post("/", response={200: BatchCreateOut, 400: dict, 404: dict})
def create_batch(request, payload: BatchCreateIn):
    try:
        campaign = Campaign.objects.select_related("script").get(pk=payload.campaign_id, is_active=True)
    except Campaign.DoesNotExist:
        return 404, {"detail": "Campaign not found or inactive."}

    script = campaign.script
    if script is None:
        return 400, {"detail": "Campaign has no script assigned."}

    for call in payload.calls:
        missing = [p for p in script.input_params if p not in call.input_params]
        if missing:
            return 400, {"detail": f"Missing input params: {', '.join(missing)}"}

    job = BatchJob.objects.create(
        campaign=campaign,
        source="api",
        total_calls=len(payload.calls),
        status="running",
    )
    items = [
        BatchCallItem(
            batch_job=job,
            phone_number=c.phone_number,
            input_params=c.input_params,
        )
        for c in payload.calls
    ]
    BatchCallItem.objects.bulk_create(items)
    for item in BatchCallItem.objects.filter(batch_job=job):
        process_batch_item.delay(item.id)

    return 200, BatchCreateOut(batch_job_id=job.id, total_calls=job.total_calls, status="pending")
```

- [ ] **Step 4: Wire router**

In `call-workspace/api/v1/router.py`, add:
```python
from .batch import router as batch_router

api.add_router("/batch", batch_router)
```

- [ ] **Step 5: Install pytest-mock if missing**

```bash
pip install pytest-mock
```
Add `pytest-mock>=3.14` to `requirements-dev.txt` (create if missing).

- [ ] **Step 6: Run tests**

```bash
pytest call-workspace/api/v1/tests/test_batch_api.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add call-workspace/api/v1/batch.py call-workspace/api/v1/router.py call-workspace/api/v1/tests
git commit -m "feat(api): POST /api/v1/batch/ for programmatic batch creation"
```

---

## Phase 6 — Webhook Receiver + Gemini Analysis

### Task 6.1: Gemini analysis service (TDD with mocked Vertex AI)

**Files:**
- Create: `call-workspace/apps/calls/services/__init__.py` (empty)
- Create: `call-workspace/apps/calls/services/gemini_analysis.py`
- Create: `call-workspace/apps/calls/tests/__init__.py` (empty)
- Create: `call-workspace/apps/calls/tests/test_gemini_analysis.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/calls/tests/test_gemini_analysis.py`:
```python
import json
from unittest.mock import MagicMock, patch

from apps.calls.services.gemini_analysis import (
    AnalysisResult,
    build_analysis_prompt,
    extract_analysis,
)


def test_build_analysis_prompt_includes_output_params_and_transcript():
    transcript = [
        {"role": "bot", "text": "Hola Juan", "timestamp": 0.0},
        {"role": "client", "text": "Hola, sí confirmo", "timestamp": 2.0},
    ]
    prompt = build_analysis_prompt(transcript=transcript, output_params=["confirmacion", "fecha"])
    assert "confirmacion" in prompt
    assert "fecha" in prompt
    assert "Hola Juan" in prompt
    assert "Hola, sí confirmo" in prompt


@patch("apps.calls.services.gemini_analysis.GenerativeModel")
def test_extract_analysis_parses_gemini_json_response(mock_model_cls):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "output_data": {"confirmacion": True, "fecha": "13 mayo"},
        "summary": "El cliente confirmó.",
        "compliance_score": 9,
    })
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp
    mock_model_cls.return_value = mock_model

    result = extract_analysis(
        transcript=[{"role": "client", "text": "sí"}],
        output_params=["confirmacion", "fecha"],
        model_name="gemini-2.5-pro",
    )

    assert isinstance(result, AnalysisResult)
    assert result.output_data == {"confirmacion": True, "fecha": "13 mayo"}
    assert result.summary == "El cliente confirmó."
    assert result.compliance_score == 9


@patch("apps.calls.services.gemini_analysis.GenerativeModel")
def test_extract_analysis_handles_markdown_wrapped_json(mock_model_cls):
    mock_resp = MagicMock()
    mock_resp.text = "```json\n" + json.dumps({
        "output_data": {"x": "y"},
        "summary": "ok",
        "compliance_score": 5,
    }) + "\n```"
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_resp
    mock_model_cls.return_value = mock_model

    result = extract_analysis(transcript=[], output_params=["x"], model_name="gemini-2.5-pro")
    assert result.output_data == {"x": "y"}
```

- [ ] **Step 2: Run test (verify fail)**

```bash
cd call-workspace
pytest apps/calls/tests/test_gemini_analysis.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement Gemini analysis service**

`call-workspace/apps/calls/services/gemini_analysis.py`:
```python
"""Post-call analysis: feed transcript to Gemini, get structured JSON back."""

import json
import re
from dataclasses import dataclass

import vertexai
from django.conf import settings
from vertexai.generative_models import GenerativeModel


@dataclass(frozen=True)
class AnalysisResult:
    output_data: dict
    summary: str
    compliance_score: int


_SYSTEM_INSTRUCTION = (
    "Eres un analista de llamadas. Recibirás el transcript de una llamada entre "
    "un bot y un cliente. Debes responder ÚNICAMENTE con un objeto JSON válido con "
    "exactamente estas claves: output_data (objeto con los datos pedidos, null si no "
    "se obtuvieron), summary (resumen en español de 2-3 oraciones), compliance_score "
    "(entero 1-10, qué tan bien el bot siguió el objetivo de la llamada)."
)


def build_analysis_prompt(*, transcript: list[dict], output_params: list[str]) -> str:
    transcript_text = "\n".join(
        f"{turn['role'].upper()}: {turn['text']}" for turn in transcript
    )
    fields = ", ".join(output_params) if output_params else "(ninguno)"
    return (
        f"Datos a extraer (claves del JSON output_data): {fields}\n\n"
        f"Transcript de la llamada:\n{transcript_text}\n\n"
        "Responde con el JSON pedido."
    )


def extract_analysis(
    *,
    transcript: list[dict],
    output_params: list[str],
    model_name: str,
) -> AnalysisResult:
    vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_REGION)
    model = GenerativeModel(model_name, system_instruction=[_SYSTEM_INSTRUCTION])
    response = model.generate_content(
        build_analysis_prompt(transcript=transcript, output_params=output_params),
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )
    raw = response.text or ""
    payload = _parse_json(raw)
    return AnalysisResult(
        output_data=payload.get("output_data") or {},
        summary=payload.get("summary", ""),
        compliance_score=int(payload.get("compliance_score") or 0),
    )


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text)
```

- [ ] **Step 4: Run test (verify pass)**

```bash
pytest apps/calls/tests/test_gemini_analysis.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/calls/services call-workspace/apps/calls/tests
git commit -m "feat(calls): Gemini 2.5 post-call analysis service"
```

---

### Task 6.2: Celery task that runs the analysis and saves CallAnalysis

**Files:**
- Create: `call-workspace/apps/calls/tasks.py`
- Create: `call-workspace/apps/calls/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/calls/tests/test_tasks.py`:
```python
from unittest.mock import patch

import pytest

from apps.calls.models import Call, CallAnalysis
from apps.calls.services.gemini_analysis import AnalysisResult
from apps.calls.tasks import analyze_call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def call(db):
    script = Script.objects.create(
        name="s",
        prompt_template="[[confirmacion]] [[fecha]]",
        greeting="hola",
    )
    campaign = Campaign.objects.create(name="c", script=script)
    return Call.objects.create(
        campaign=campaign,
        phone_number="+1",
        status="analyzing",
        transcript=[{"role": "client", "text": "sí"}],
    )


@pytest.mark.django_db
@patch("apps.calls.tasks.extract_analysis")
def test_analyze_call_creates_analysis(mock_extract, call):
    mock_extract.return_value = AnalysisResult(
        output_data={"confirmacion": True, "fecha": "13 mayo"},
        summary="confirmó",
        compliance_score=9,
    )
    analyze_call(str(call.id))
    call.refresh_from_db()
    assert call.status == "done"
    assert call.analysis.output_data == {"confirmacion": True, "fecha": "13 mayo"}
    assert call.analysis.compliance_score == 9


@pytest.mark.django_db
@patch("apps.calls.tasks.extract_analysis", side_effect=ValueError("bad json"))
def test_analyze_call_marks_error_on_failure(mock_extract, call):
    with pytest.raises(ValueError):
        analyze_call(str(call.id))
    call.refresh_from_db()
    assert call.status == "error"
    assert "bad json" in call.error_message
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest apps/calls/tests/test_tasks.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement task**

`call-workspace/apps/calls/tasks.py`:
```python
from celery import shared_task
from django.conf import settings
from django.db import transaction

from apps.batch.models import BatchJob

from .models import Call, CallAnalysis
from .services.gemini_analysis import extract_analysis


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_call(self, call_id: str) -> None:
    call = Call.objects.select_related("campaign__script", "batch_item__batch_job").get(pk=call_id)
    output_params = call.campaign.script.output_params if call.campaign.script else []

    try:
        result = extract_analysis(
            transcript=call.transcript,
            output_params=output_params,
            model_name=settings.GEMINI_MODEL,
        )
    except Exception as exc:
        call.status = "error"
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message"])
        raise

    with transaction.atomic():
        CallAnalysis.objects.update_or_create(
            call=call,
            defaults={
                "output_data": result.output_data,
                "summary": result.summary,
                "compliance_score": result.compliance_score,
                "llm_model": settings.GEMINI_MODEL,
            },
        )
        call.status = "done"
        call.save(update_fields=["status"])

        if call.batch_item:
            item = call.batch_item
            item.status = "done"
            item.save(update_fields=["status"])
            job: BatchJob = item.batch_job
            BatchJob.objects.filter(pk=job.pk).update(done_calls=job.done_calls + 1)
            if job.done_calls + 1 + job.failed_calls >= job.total_calls:
                BatchJob.objects.filter(pk=job.pk).update(status="completed")
```

- [ ] **Step 4: Run tests**

```bash
pytest apps/calls/tests/test_tasks.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add call-workspace/apps/calls/tasks.py call-workspace/apps/calls/tests/test_tasks.py
git commit -m "feat(calls): Celery task that runs Gemini analysis post-webhook"
```

---

### Task 6.3: Webhook receiver endpoint

**Files:**
- Create: `call-workspace/api/v1/webhook.py` (schemas + endpoint)
- Modify: `call-workspace/api/v1/router.py`
- Create: `call-workspace/apps/calls/tests/test_webhook.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/calls/tests/test_webhook.py`:
```python
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from apps.calls.models import Call
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def call(db):
    s = Script.objects.create(name="s", prompt_template="x [[ok]]", greeting="hi")
    c = Campaign.objects.create(name="c", script=s)
    return Call.objects.create(
        campaign=c,
        phone_number="+1",
        status="calling",
        started_at=datetime.now(timezone.utc),
    )


@pytest.mark.django_db
@patch("api.v1.webhook.analyze_call.delay")
def test_webhook_updates_call_and_enqueues_analysis(mock_delay, client, call):
    payload = {
        "call_id": str(call.id),
        "status": "completed",
        "duration_seconds": 42,
        "audio_gcs_url": "gs://b/audio.wav",
        "transcript": [
            {"role": "bot", "text": "Hola", "timestamp": 0.0},
            {"role": "client", "text": "sí", "timestamp": 2.0},
        ],
    }
    response = client.post("/api/v1/calls/webhook/", data=payload, content_type="application/json")
    assert response.status_code == 200
    call.refresh_from_db()
    assert call.status == "analyzing"
    assert call.duration_seconds == 42
    assert call.audio_gcs_url == "gs://b/audio.wav"
    assert len(call.transcript) == 2
    mock_delay.assert_called_once_with(str(call.id))


@pytest.mark.django_db
def test_webhook_unknown_call_returns_404(client):
    response = client.post(
        "/api/v1/calls/webhook/",
        data={
            "call_id": "00000000-0000-0000-0000-000000000000",
            "status": "completed",
            "duration_seconds": 1,
            "audio_gcs_url": "",
            "transcript": [],
        },
        content_type="application/json",
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest apps/calls/tests/test_webhook.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement webhook endpoint**

`call-workspace/api/v1/webhook.py`:
```python
from datetime import datetime, timezone

from ninja import Router, Schema

from apps.calls.models import Call
from apps.calls.tasks import analyze_call

router = Router()


class TranscriptTurn(Schema):
    role: str
    text: str
    timestamp: float | None = None


class CallWebhookIn(Schema):
    call_id: str
    status: str
    duration_seconds: int
    audio_gcs_url: str
    transcript: list[TranscriptTurn]


@router.post("/webhook/", auth=None, response={200: dict, 404: dict})
def call_completed_webhook(request, payload: CallWebhookIn):
    try:
        call = Call.objects.get(pk=payload.call_id)
    except Call.DoesNotExist:
        return 404, {"detail": "call not found"}

    call.status = "analyzing"
    call.duration_seconds = payload.duration_seconds
    call.audio_gcs_url = payload.audio_gcs_url
    call.transcript = [turn.dict() for turn in payload.transcript]
    call.ended_at = datetime.now(timezone.utc)
    call.save(update_fields=["status", "duration_seconds", "audio_gcs_url", "transcript", "ended_at"])

    analyze_call.delay(str(call.id))
    return 200, {"received": True}
```

- [ ] **Step 4: Wire router**

In `call-workspace/api/v1/router.py`:
```python
from .webhook import router as webhook_router

api.add_router("/calls", webhook_router)
```

- [ ] **Step 5: Run test**

```bash
pytest apps/calls/tests/test_webhook.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add call-workspace/api/v1/webhook.py call-workspace/api/v1/router.py call-workspace/apps/calls/tests/test_webhook.py
git commit -m "feat(api): POST /api/v1/calls/webhook/ receiver for BOT_VOZ callbacks"
```

---

### Task 6.4: Orphan call sweeper (Celery beat)

**Files:**
- Modify: `call-workspace/apps/calls/tasks.py` (add sweeper task)
- Modify: `call-workspace/config/settings/base.py` (add CELERY_BEAT_SCHEDULE)
- Create: `call-workspace/apps/calls/tests/test_sweeper.py`

- [ ] **Step 1: Write the failing test**

`call-workspace/apps/calls/tests/test_sweeper.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest

from apps.calls.models import Call
from apps.calls.tasks import sweep_orphan_calls
from apps.campaigns.models import Campaign
from apps.scripts.models import Script


@pytest.fixture
def campaign(db):
    s = Script.objects.create(name="s", prompt_template="x", greeting="hi")
    return Campaign.objects.create(name="c", script=s)


@pytest.mark.django_db
def test_sweeper_marks_stuck_calls_as_error(campaign):
    old_ts = datetime.now(timezone.utc) - timedelta(minutes=15)
    stuck = Call.objects.create(
        campaign=campaign, phone_number="+1", status="calling", started_at=old_ts,
    )
    fresh = Call.objects.create(
        campaign=campaign, phone_number="+2", status="calling",
        started_at=datetime.now(timezone.utc),
    )

    swept = sweep_orphan_calls()

    stuck.refresh_from_db()
    fresh.refresh_from_db()
    assert stuck.status == "error"
    assert "orphan" in stuck.error_message.lower()
    assert fresh.status == "calling"
    assert swept == 1
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest apps/calls/tests/test_sweeper.py -v
```
Expected: FAIL with `cannot import name 'sweep_orphan_calls'`.

- [ ] **Step 3: Add sweeper to `apps/calls/tasks.py`**

Append to the existing file:
```python
from datetime import datetime, timedelta, timezone


@shared_task
def sweep_orphan_calls() -> int:
    """Mark calls stuck in 'calling' status for > 10 minutes as error."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stuck = Call.objects.filter(status="calling", started_at__lt=cutoff)
    count = stuck.count()
    stuck.update(status="error", error_message="orphan call: no webhook within 10 minutes")
    return count
```

- [ ] **Step 4: Schedule it in settings**

In `call-workspace/config/settings/base.py`, add at the bottom:
```python
CELERY_BEAT_SCHEDULE = {
    "sweep-orphan-calls": {
        "task": "apps.calls.tasks.sweep_orphan_calls",
        "schedule": 900.0,  # every 15 minutes
    },
}
```

- [ ] **Step 5: Run test**

```bash
pytest apps/calls/tests/test_sweeper.py -v
```
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add call-workspace/apps/calls/tasks.py call-workspace/apps/calls/tests/test_sweeper.py call-workspace/config/settings/base.py
git commit -m "feat(calls): Celery beat sweeper for orphan calls (>10min)"
```

---

## Phase 7 — Dashboard Polish

### Task 7.1: Dashboard with KPIs + per-campaign chart + [[params]] distribution

**Files:**
- Modify: `call-workspace/apps/calls/views.py` (dashboard_view)
- Modify: `call-workspace/templates/dashboard.html`

- [ ] **Step 1: Replace `dashboard_view` in `apps/calls/views.py`**

```python
from collections import Counter

from django.db.models import Avg, Count

from apps.batch.models import BatchJob
from apps.campaigns.models import Campaign

from .models import Call, CallAnalysis


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

    # Param distribution for the most recently active campaign with a script
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
```

- [ ] **Step 2: Replace `templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="p-6">
  <h1 class="text-2xl font-bold mb-6">Dashboard</h1>

  <div class="grid grid-cols-4 gap-4 mb-6">
    <div class="bg-white p-4 rounded shadow"><div class="text-3xl font-bold">{{ total_calls }}</div><div class="text-gray-500 text-sm">Llamadas</div></div>
    <div class="bg-white p-4 rounded shadow"><div class="text-3xl font-bold">{{ contact_rate }}%</div><div class="text-gray-500 text-sm">Contacto</div></div>
    <div class="bg-white p-4 rounded shadow"><div class="text-3xl font-bold">{{ avg_score }}/10</div><div class="text-gray-500 text-sm">Score promedio</div></div>
    <div class="bg-white p-4 rounded shadow"><div class="text-3xl font-bold">{{ active_batches }}</div><div class="text-gray-500 text-sm">Lotes activos</div></div>
  </div>

  <div class="grid grid-cols-2 gap-4">
    <div class="bg-white p-4 rounded shadow">
      <h2 class="font-bold mb-2">Score por campaña</h2>
      <canvas id="campaignChart" height="220"></canvas>
    </div>
    <div class="bg-white p-4 rounded shadow">
      <h2 class="font-bold mb-2">
        Distribución de [[params]]
        {% if active_campaign %}<span class="text-sm text-gray-500">— {{ active_campaign.name }}</span>{% endif %}
      </h2>
      {% for param, counts in param_distribution.items %}
      <div class="mb-3">
        <div class="font-medium text-sm">{{ param }}</div>
        {% for key, val in counts.items %}
        <div class="flex items-center text-sm">
          <div class="w-20 truncate">{{ key }}</div>
          <div class="flex-1 bg-gray-200 h-3 rounded mx-2"><div class="bg-blue-500 h-3 rounded" style="width: {% widthratio val 1 5 %}px"></div></div>
          <div class="w-10 text-right">{{ val }}</div>
        </div>
        {% endfor %}
      </div>
      {% empty %}
      <p class="text-gray-500 text-sm">Sin datos aún.</p>
      {% endfor %}
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const labels = [{% for c in per_campaign %}"{{ c.name|escapejs }}"{% if not forloop.last %},{% endif %}{% endfor %}];
const data = [{% for c in per_campaign %}{{ c.avg_score|default:0|stringformat:".1f" }}{% if not forloop.last %},{% endif %}{% endfor %}];
new Chart(document.getElementById("campaignChart"), {
  type: "bar",
  data: { labels, datasets: [{ label: "Score promedio", data, backgroundColor: "rgba(37,99,235,0.6)" }] },
  options: { scales: { y: { beginAtZero: true, max: 10 } } }
});
</script>
{% endblock %}
```

- [ ] **Step 3: Verify**

```bash
python manage.py check
```
Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add call-workspace/apps/calls/views.py call-workspace/templates/dashboard.html
git commit -m "feat(dashboard): KPIs, per-campaign chart, [[params]] distribution"
```

---

### Task 7.2: Call detail with audio player + [[params]] card

**Files:**
- Create: `call-workspace/apps/calls/services/gcs_audio.py`
- Create: `call-workspace/apps/calls/tests/test_gcs_audio.py`
- Modify: `call-workspace/apps/calls/views.py` (detail_view, add re-analyze)
- Modify: `call-workspace/apps/calls/urls.py`
- Replace: `call-workspace/templates/calls/detail.html`

- [ ] **Step 1: Write the failing test for signed URL**

`call-workspace/apps/calls/tests/test_gcs_audio.py`:
```python
from unittest.mock import MagicMock, patch

from apps.calls.services.gcs_audio import generate_signed_url


@patch("apps.calls.services.gcs_audio.storage.Client")
def test_generate_signed_url_builds_correct_path(mock_client_cls):
    bucket = MagicMock()
    blob = MagicMock()
    blob.generate_signed_url.return_value = "https://signed/url"
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_client_cls.return_value = client

    result = generate_signed_url("gs://my-bucket/calls/abc.wav", expires_minutes=60)

    assert result == "https://signed/url"
    client.bucket.assert_called_once_with("my-bucket")
    bucket.blob.assert_called_once_with("calls/abc.wav")
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest apps/calls/tests/test_gcs_audio.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement signed URL helper**

`call-workspace/apps/calls/services/gcs_audio.py`:
```python
from datetime import timedelta

from google.cloud import storage


def generate_signed_url(gcs_url: str, expires_minutes: int = 60) -> str:
    if not gcs_url.startswith("gs://"):
        raise ValueError(f"Not a GCS URL: {gcs_url}")
    path = gcs_url[len("gs://"):]
    bucket_name, _, object_name = path.partition("/")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expires_minutes),
        method="GET",
    )
```

- [ ] **Step 4: Run test**

```bash
pytest apps/calls/tests/test_gcs_audio.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Update detail view to generate signed URL and accept re-analyze**

Modify `call-workspace/apps/calls/views.py` `detail_view`:
```python
from .services.gcs_audio import generate_signed_url
from .tasks import analyze_call


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
```

In `apps/calls/urls.py`, add:
```python
path("<uuid:pk>/reanalyze/", views.reanalyze_view, name="reanalyze"),
```

- [ ] **Step 6: Replace `templates/calls/detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<div class="p-6 max-w-4xl">
  <h1 class="text-2xl font-bold mb-2">Llamada {{ call.phone_number }}</h1>
  <p class="text-sm text-gray-500 mb-4">ID: {{ call.id }} · {{ call.created_at|date:"Y-m-d H:i" }} · {{ call.get_status_display }}</p>

  {% if audio_url %}
  <div class="bg-white p-4 rounded shadow mb-4">
    <h2 class="font-bold mb-2">Audio</h2>
    <audio controls src="{{ audio_url }}" class="w-full"></audio>
  </div>
  {% endif %}

  {% if call.analysis %}
  <div class="bg-white p-4 rounded shadow mb-4">
    <h2 class="font-bold mb-2">Datos recolectados</h2>
    <pre class="bg-gray-50 p-3 rounded text-sm">{{ call.analysis.output_data|safe }}</pre>
    <div class="mt-3 text-sm"><strong>Score:</strong> {{ call.analysis.compliance_score }}/10</div>
    <div class="mt-1 text-sm"><strong>Resumen:</strong> {{ call.analysis.summary }}</div>
    <form method="post" action="{% url 'calls:reanalyze' call.pk %}" class="mt-3">
      {% csrf_token %}
      <button class="text-sm text-blue-600">Re-analizar</button>
    </form>
  </div>
  {% endif %}

  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-bold mb-2">Transcript</h2>
    <div class="space-y-2 text-sm">
      {% for turn in call.transcript %}
        <div class="{% if turn.role == 'bot' %}text-blue-700{% else %}text-gray-800{% endif %}">
          <span class="font-bold uppercase text-xs">{{ turn.role }}</span>
          <span class="text-xs text-gray-400">{{ turn.timestamp|default:"" }}</span>
          <div>{{ turn.text }}</div>
        </div>
      {% empty %}
        <p class="text-gray-500">Sin transcript.</p>
      {% endfor %}
    </div>
  </div>

  {% if call.error_message %}
  <div class="mt-4 bg-red-50 text-red-700 p-3 rounded text-sm">{{ call.error_message }}</div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Commit**

```bash
git add call-workspace/apps/calls call-workspace/templates/calls/detail.html
git commit -m "feat(calls): detail view with signed audio URL + [[params]] + re-analyze"
```

---

## Phase 8 — Verification

### Task 8.1: Run full test suite + database migrate against SQL Server

**Files:** none

- [ ] **Step 1: Run all tests (sqlite in-memory by default)**

```bash
cd call-workspace
pytest -v
```
Expected: all tests pass. List of test files:
- `apps/scripts/tests/test_parsers.py` (8 tests)
- `apps/scripts/tests/test_models.py` (3)
- `apps/scripts/tests/test_views.py` (2)
- `apps/batch/tests/test_csv_validator.py` (5)
- `apps/batch/tests/test_services.py` (3)
- `apps/batch/tests/test_tasks.py` (2)
- `api/v1/tests/test_batch_api.py` (2)
- `apps/calls/tests/test_gemini_analysis.py` (3)
- `apps/calls/tests/test_tasks.py` (2)
- `apps/calls/tests/test_webhook.py` (2)
- `apps/calls/tests/test_sweeper.py` (1)
- `apps/calls/tests/test_gcs_audio.py` (1)

Total: 34 tests.

- [ ] **Step 2: Run migration check against a real SQL Server**

Spin up SQL Server (docker-compose or local instance), set env vars in `.env`, then:
```bash
cd call-workspace
python manage.py migrate
```
Expected: all migrations applied, no errors.

- [ ] **Step 3: Create superuser and smoke-check the UI**

```bash
python manage.py createsuperuser
python manage.py runserver
```
Visit `http://localhost:8000/admin/`, `http://localhost:8000/scripts/`, `http://localhost:8000/campaigns/`, `http://localhost:8000/batch/`. Confirm each loads.

- [ ] **Step 4: Commit any final tweaks**

```bash
git add -A
git commit -m "test: full suite passing + SQL Server migrations verified" || echo "No changes"
```

---

## Self-Review Notes

- **Spec coverage:** ✅
  - SQL Server: Task 1.2
  - Removed AssemblyAI/OpenRouter/FTP: Task 1.3
  - Script with `{{}}`/`[[]]` syntax: Tasks 2.2–2.4
  - Campaign FK to Script: Task 3.1
  - Call/CallAnalysis models: Tasks 4.1, 5.2
  - BatchJob/BatchCallItem + CSV + REST API: Tasks 5.1–5.7
  - Webhook receiver: Task 6.3
  - Gemini 2.5 analysis: Tasks 6.1, 6.2
  - Orphan call sweeper (10 min): Task 6.4
  - Dashboard with KPIs + per-campaign + [[params]] distribution: Task 7.1
  - Call detail with audio player + [[params]] + re-analyze: Task 7.2

- **No placeholders:** verified — every code step has full implementation.

- **Type consistency:** `parse_template` returns `ParsedTemplate` (Tasks 2.2, 2.3 use the same name). `extract_analysis` returns `AnalysisResult` (consistent in 6.1, 6.2). `dispatch_call` and `build_call_payload` consistent (5.4, 5.5). `process_batch_item` and `analyze_call` Celery task names consistent across files.
