# Plan B — BOT_VOZ Integration (Execution Microservice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform BOT_VOZ from a YAML-profile-driven inbound voice bot into a Django-controlled outbound execution microservice: accepts call requests via `POST /calls/initiate` with a fully rendered prompt, uses Gemini 2.5 Pro during the call, uploads the recorded audio to GCS, and notifies Django via webhook on hangup.

**Architecture:** FastAPI + asyncio (existing). New `/calls/initiate` endpoint replaces the YAML-loaded bot profile flow for outbound calls — the prompt and output params now arrive dynamically with each call. After hangup, the orchestrator uploads audio to GCS and POSTs the transcript + audio URL to Django's `/api/v1/calls/webhook/`.

**Tech Stack:** Python 3.12, FastAPI, asyncio, Telnyx, LiveKit, Google Cloud STT, Google Cloud TTS, Vertex AI (Gemini 2.5), Google Cloud Storage, httpx.

---

## File Structure

**New files:**

```
src/
├── api/routes/
│   └── calls.py                       NEW — POST /calls/initiate endpoint
├── integrations/
│   ├── __init__.py                    NEW package
│   ├── django_webhook.py              NEW — POST webhook to Django
│   └── gcs_audio.py                   NEW — upload .wav to GCS
└── orchestrator/
    └── outbound_orchestrator.py       NEW — orchestrator variant for /calls/initiate
tests/unit/
├── test_calls_endpoint.py             NEW
├── test_django_webhook.py             NEW
├── test_gcs_audio.py                  NEW
└── test_outbound_orchestrator.py      NEW
```

**Modified files:**

```
config/settings.py                     ADD gemini_model="gemini-2.5-pro", gcs_audio_bucket, django_webhook_*
src/api/app.py                         REGISTER new calls router
src/llm/gemini_client.py               UPGRADE to 2.5 model
src/llm/prompt_builder.py              NEW: build_dynamic_system_prompt(rendered_prompt, output_params)
src/orchestrator/call_orchestrator.py  ACCEPT dynamic prompt + output_params + webhook_url
src/session/session_state.py           STORE transcript turns with role+timestamp+text
requirements.txt                       ADD google-cloud-storage, httpx
```

---

## Phase 1 — Settings & Dependencies

### Task 1.1: Add new settings and dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `config/settings.py`
- Modify: `.env.example`

- [ ] **Step 1: Add packages to `requirements.txt`**

Append these lines to `requirements.txt` (if not already present):
```
google-cloud-storage>=2.18
httpx>=0.27
```

- [ ] **Step 2: Add settings fields**

In `config/settings.py`, locate the `Settings` class (pydantic-settings BaseSettings). Add:

```python
    # Gemini model
    gemini_model: str = "gemini-2.5-pro"

    # GCS for call audio
    gcs_audio_bucket: str = ""

    # Django webhook (where to POST on call end)
    django_webhook_timeout_seconds: int = 10
```

- [ ] **Step 3: Update `.env.example`**

Append at the bottom:
```
GEMINI_MODEL=gemini-2.5-pro
GCS_AUDIO_BUCKET=botvoz-call-audio
DJANGO_WEBHOOK_TIMEOUT_SECONDS=10
```

- [ ] **Step 4: Verify config loads**

```bash
python -c "from config.settings import get_settings; s = get_settings(); print(s.gemini_model)"
```
Expected: `gemini-2.5-pro`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config/settings.py .env.example
git commit -m "chore(config): add Gemini 2.5 model, GCS bucket, webhook timeout"
```

---

## Phase 2 — Gemini 2.5 Upgrade

### Task 2.1: Upgrade Gemini client model

**Files:**
- Modify: `src/llm/gemini_client.py`
- Modify: `tests/unit/test_gemini_client.py` (create if missing)

- [ ] **Step 1: Inspect current Gemini client**

Read `src/llm/gemini_client.py`. Locate the model name string (currently `"gemini-2.0-flash"` or similar) and how it's instantiated.

- [ ] **Step 2: Make the model name configurable via settings**

Replace the hardcoded model name with `settings.gemini_model`. The instantiation should look like:

```python
from config.settings import get_settings

settings = get_settings()
self._model = GenerativeModel(settings.gemini_model, ...)
```

(If the client receives the model name in __init__, default the constructor parameter from settings.)

- [ ] **Step 3: Write a minimal sanity test**

`tests/unit/test_gemini_client.py` (create or append):
```python
from unittest.mock import patch

from src.llm.gemini_client import GeminiClient


@patch("src.llm.gemini_client.GenerativeModel")
@patch("src.llm.gemini_client.vertexai.init")
def test_gemini_client_uses_configured_model(mock_init, mock_model_cls):
    GeminiClient()
    args, kwargs = mock_model_cls.call_args
    # First positional arg or "model_name" kwarg should be the configured model
    assert args[0] == "gemini-2.5-pro" or kwargs.get("model_name") == "gemini-2.5-pro"
```

(Adapt the import path and class name to match the actual implementation.)

- [ ] **Step 4: Run the test**

```bash
pytest tests/unit/test_gemini_client.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/llm/gemini_client.py tests/unit/test_gemini_client.py
git commit -m "feat(llm): upgrade Gemini client to 2.5 Pro via settings"
```

---

## Phase 3 — Dynamic Prompt Builder

### Task 3.1: Build prompt with rendered text + output_params instructions (TDD)

**Files:**
- Modify: `src/llm/prompt_builder.py` (or create if missing)
- Create: `tests/unit/test_prompt_builder.py`

- [ ] **Step 1: Inspect current prompt builder**

Read `src/llm/prompt_builder.py`. Note its existing function signatures. The current builder reads from a `BotProfile`. We need a new function `build_dynamic_system_prompt(rendered_prompt: str, output_params: list[str]) -> str` that doesn't depend on profiles.

- [ ] **Step 2: Write failing test**

`tests/unit/test_prompt_builder.py`:
```python
from src.llm.prompt_builder import build_dynamic_system_prompt


def test_returns_prompt_unchanged_when_no_output_params():
    result = build_dynamic_system_prompt("Hola, soy un bot.", output_params=[])
    assert result == "Hola, soy un bot."


def test_appends_collection_instructions_when_output_params_present():
    result = build_dynamic_system_prompt(
        "Hola, soy un bot.", output_params=["confirmacion", "fecha"]
    )
    assert "Hola, soy un bot." in result
    assert "confirmacion" in result
    assert "fecha" in result


def test_includes_temporal_resolution_instruction():
    result = build_dynamic_system_prompt(
        "x", output_params=["fecha"]
    )
    assert "mañana" in result.lower() or "fecha" in result.lower()
```

- [ ] **Step 3: Run test (verify fail)**

```bash
pytest tests/unit/test_prompt_builder.py -v
```
Expected: FAIL with `cannot import name 'build_dynamic_system_prompt'`.

- [ ] **Step 4: Implement the function**

Append to `src/llm/prompt_builder.py`:

```python
def build_dynamic_system_prompt(rendered_prompt: str, output_params: list[str]) -> str:
    """Append [[output_params]] collection instructions to an already-rendered prompt."""
    if not output_params:
        return rendered_prompt

    fields = ", ".join(output_params)
    instructions = (
        f"\n\n[Instrucciones del sistema] Al final de la conversación debes haber "
        f"intentado recolectar los siguientes datos del cliente: {fields}. "
        f"Si no logras obtener alguno, deja null. Cuando el cliente mencione "
        f'fechas relativas (como "mañana" o "el jueves"), calcula la fecha exacta '
        f"basándote en la fecha actual y confírmala con el cliente antes de cerrar."
    )
    return rendered_prompt + instructions
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_prompt_builder.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/llm/prompt_builder.py tests/unit/test_prompt_builder.py
git commit -m "feat(llm): dynamic system prompt builder with [[output]] instructions"
```

---

## Phase 4 — GCS Audio Upload

### Task 4.1: GCS audio uploader (TDD with mocked google-cloud-storage)

**Files:**
- Create: `src/integrations/__init__.py` (empty)
- Create: `src/integrations/gcs_audio.py`
- Create: `tests/unit/test_gcs_audio.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_gcs_audio.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.gcs_audio import upload_call_audio


@pytest.mark.asyncio
@patch("src.integrations.gcs_audio.storage.Client")
async def test_upload_returns_gcs_url(mock_client_cls, tmp_path):
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake-wav-bytes")

    bucket = MagicMock()
    blob = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    mock_client_cls.return_value = client

    url = await upload_call_audio(
        bucket_name="my-bucket",
        call_id="abc-123",
        local_path=str(audio_file),
    )
    assert url == "gs://my-bucket/calls/abc-123.wav"
    bucket.blob.assert_called_once_with("calls/abc-123.wav")
    blob.upload_from_filename.assert_called_once_with(str(audio_file), content_type="audio/wav")


@pytest.mark.asyncio
@patch("src.integrations.gcs_audio.storage.Client")
async def test_upload_raises_when_bucket_name_empty(mock_client_cls, tmp_path):
    f = tmp_path / "a.wav"
    f.write_bytes(b"x")
    with pytest.raises(ValueError, match="bucket"):
        await upload_call_audio(bucket_name="", call_id="x", local_path=str(f))
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest tests/unit/test_gcs_audio.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.integrations'`.

- [ ] **Step 3: Implement uploader**

`src/integrations/__init__.py`: empty file.

`src/integrations/gcs_audio.py`:
```python
"""Upload recorded call audio to Google Cloud Storage."""

import asyncio

from google.cloud import storage


async def upload_call_audio(*, bucket_name: str, call_id: str, local_path: str) -> str:
    """Upload a WAV file to gs://<bucket_name>/calls/<call_id>.wav and return the gs:// URL."""
    if not bucket_name:
        raise ValueError("bucket_name is required")

    def _do_upload() -> str:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"calls/{call_id}.wav")
        blob.upload_from_filename(local_path, content_type="audio/wav")
        return f"gs://{bucket_name}/calls/{call_id}.wav"

    return await asyncio.to_thread(_do_upload)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_gcs_audio.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/integrations tests/unit/test_gcs_audio.py
git commit -m "feat(integrations): GCS audio uploader for completed call recordings"
```

---

## Phase 5 — Django Webhook Client

### Task 5.1: Django webhook client (TDD with mocked httpx.AsyncClient)

**Files:**
- Create: `src/integrations/django_webhook.py`
- Create: `tests/unit/test_django_webhook.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_django_webhook.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.django_webhook import (
    CallCompletedPayload,
    DjangoWebhookError,
    notify_call_completed,
)


@pytest.fixture
def payload():
    return CallCompletedPayload(
        call_id="abc",
        status="completed",
        duration_seconds=42,
        audio_gcs_url="gs://b/a.wav",
        transcript=[
            {"role": "bot", "text": "Hola", "timestamp": 0.0},
            {"role": "client", "text": "Sí", "timestamp": 2.0},
        ],
    )


@pytest.mark.asyncio
@patch("src.integrations.django_webhook.httpx.AsyncClient")
async def test_posts_payload_to_url(mock_client_cls, payload):
    response = MagicMock(status_code=200)
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post = AsyncMock(return_value=response)
    mock_client_cls.return_value = client

    await notify_call_completed(
        webhook_url="https://django/api/v1/calls/webhook/", payload=payload, timeout=10
    )

    client.post.assert_awaited_once()
    args, kwargs = client.post.call_args
    assert args[0] == "https://django/api/v1/calls/webhook/"
    sent = kwargs["json"]
    assert sent["call_id"] == "abc"
    assert sent["audio_gcs_url"] == "gs://b/a.wav"
    assert len(sent["transcript"]) == 2


@pytest.mark.asyncio
@patch("src.integrations.django_webhook.httpx.AsyncClient")
async def test_raises_on_non_2xx(mock_client_cls, payload):
    import httpx as _httpx
    response = MagicMock(status_code=500, text="Boom")
    response.raise_for_status = MagicMock(
        side_effect=_httpx.HTTPStatusError("err", request=MagicMock(), response=response)
    )
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post = AsyncMock(return_value=response)
    mock_client_cls.return_value = client

    with pytest.raises(DjangoWebhookError):
        await notify_call_completed(
            webhook_url="https://django/x", payload=payload, timeout=10
        )
```

- [ ] **Step 2: Install pytest-asyncio if missing**

```bash
pip install pytest-asyncio
```

Add to `requirements-dev.txt`:
```
pytest-asyncio>=0.23
```

And add to `pytest.ini`:
```
asyncio_mode = auto
```

- [ ] **Step 3: Run test (verify fail)**

```bash
pytest tests/unit/test_django_webhook.py -v
```
Expected: FAIL with import error.

- [ ] **Step 4: Implement webhook client**

`src/integrations/django_webhook.py`:
```python
"""HTTP client that notifies Django when a call has completed."""

from dataclasses import asdict, dataclass

import httpx


class DjangoWebhookError(RuntimeError):
    pass


@dataclass
class CallCompletedPayload:
    call_id: str
    status: str
    duration_seconds: int
    audio_gcs_url: str
    transcript: list[dict]


async def notify_call_completed(
    *, webhook_url: str, payload: CallCompletedPayload, timeout: int
) -> None:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(webhook_url, json=asdict(payload))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DjangoWebhookError(f"Webhook failed: {exc}") from exc
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_django_webhook.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/integrations/django_webhook.py tests/unit/test_django_webhook.py requirements-dev.txt pytest.ini
git commit -m "feat(integrations): async Django webhook client"
```

---

## Phase 6 — Outbound Orchestrator

The existing `CallOrchestrator` is tightly coupled to bot profiles and inbound Telnyx webhooks. Rather than rip it apart, we create a parallel `OutboundOrchestrator` that takes its config from the `/calls/initiate` request. Eventually both can be merged; for now, this isolates the new flow.

### Task 6.1: Outbound orchestrator skeleton (TDD)

**Files:**
- Create: `src/orchestrator/outbound_orchestrator.py`
- Create: `tests/unit/test_outbound_orchestrator.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_outbound_orchestrator.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.outbound_orchestrator import OutboundCallConfig, OutboundOrchestrator


@pytest.fixture
def config():
    return OutboundCallConfig(
        call_id="abc-123",
        phone_number="+1",
        rendered_prompt="Hola Juan",
        greeting="Hola Juan",
        output_params=["ok"],
        webhook_url="http://django/api/v1/calls/webhook/",
    )


@pytest.mark.asyncio
async def test_orchestrator_stores_config(config):
    orch = OutboundOrchestrator(config)
    assert orch.config.call_id == "abc-123"
    assert orch.config.output_params == ["ok"]


@pytest.mark.asyncio
async def test_orchestrator_uses_dynamic_system_prompt(config):
    orch = OutboundOrchestrator(config)
    prompt = orch.build_system_prompt()
    assert "Hola Juan" in prompt
    assert "ok" in prompt


@pytest.mark.asyncio
@patch("src.orchestrator.outbound_orchestrator.notify_call_completed", new_callable=AsyncMock)
@patch("src.orchestrator.outbound_orchestrator.upload_call_audio", new_callable=AsyncMock, return_value="gs://b/a.wav")
async def test_finalize_uploads_audio_and_notifies_django(
    mock_upload, mock_notify, config
):
    orch = OutboundOrchestrator(config)
    orch.transcript = [
        {"role": "bot", "text": "Hola", "timestamp": 0.0},
        {"role": "client", "text": "Sí", "timestamp": 2.0},
    ]
    orch.duration_seconds = 42

    await orch.finalize(local_audio_path="/tmp/a.wav", bucket_name="bucket", webhook_timeout=10)

    mock_upload.assert_awaited_once_with(
        bucket_name="bucket", call_id="abc-123", local_path="/tmp/a.wav"
    )
    mock_notify.assert_awaited_once()
    args, kwargs = mock_notify.call_args
    assert kwargs["webhook_url"] == "http://django/api/v1/calls/webhook/"
    assert kwargs["payload"].call_id == "abc-123"
    assert kwargs["payload"].audio_gcs_url == "gs://b/a.wav"
    assert kwargs["payload"].duration_seconds == 42
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest tests/unit/test_outbound_orchestrator.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement OutboundOrchestrator**

`src/orchestrator/outbound_orchestrator.py`:
```python
"""Outbound call orchestrator driven by /calls/initiate config (not YAML profiles)."""

from dataclasses import dataclass, field

import structlog

from src.integrations.django_webhook import CallCompletedPayload, notify_call_completed
from src.integrations.gcs_audio import upload_call_audio
from src.llm.prompt_builder import build_dynamic_system_prompt

logger = structlog.get_logger(__name__)


@dataclass
class OutboundCallConfig:
    call_id: str
    phone_number: str
    rendered_prompt: str
    greeting: str
    output_params: list[str]
    webhook_url: str


class OutboundOrchestrator:
    def __init__(self, config: OutboundCallConfig):
        self.config = config
        self.transcript: list[dict] = []
        self.duration_seconds: int = 0
        self.local_audio_path: str | None = None

    def build_system_prompt(self) -> str:
        return build_dynamic_system_prompt(
            self.config.rendered_prompt, self.config.output_params
        )

    def append_turn(self, role: str, text: str, timestamp: float) -> None:
        self.transcript.append({"role": role, "text": text, "timestamp": timestamp})

    async def finalize(
        self, *, local_audio_path: str, bucket_name: str, webhook_timeout: int
    ) -> None:
        audio_url = await upload_call_audio(
            bucket_name=bucket_name,
            call_id=self.config.call_id,
            local_path=local_audio_path,
        )
        payload = CallCompletedPayload(
            call_id=self.config.call_id,
            status="completed",
            duration_seconds=self.duration_seconds,
            audio_gcs_url=audio_url,
            transcript=self.transcript,
        )
        await notify_call_completed(
            webhook_url=self.config.webhook_url,
            payload=payload,
            timeout=webhook_timeout,
        )
        logger.info("call_finalized", call_id=self.config.call_id, audio_url=audio_url)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_outbound_orchestrator.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/outbound_orchestrator.py tests/unit/test_outbound_orchestrator.py
git commit -m "feat(orchestrator): outbound orchestrator with dynamic prompt + finalize"
```

---

### Task 6.2: Wire OutboundOrchestrator into the real-time pipeline

This task plugs the new orchestrator into the existing Telnyx + LiveKit + STT + Gemini + TTS pipeline. Implementation details depend on the current `CallOrchestrator` structure in `src/orchestrator/call_orchestrator.py`.

**Files:**
- Modify: `src/orchestrator/call_orchestrator.py` OR create a new outbound pipeline function

- [ ] **Step 1: Read the current `CallOrchestrator`**

Open `src/orchestrator/call_orchestrator.py`. Identify:
1. How it builds the system prompt (likely from `BotProfile`)
2. How it runs the STT → Gemini → TTS loop
3. Where it currently handles hangup (`_handle_hangup` was mentioned in the spec around lines 159–169)
4. How it knows when the call ends

- [ ] **Step 2: Add an outbound entry point**

Add a new function or class method:

```python
async def run_outbound_call(config: OutboundCallConfig) -> None:
    """Drive an outbound call to completion using the dynamic config from Django."""
    from src.orchestrator.outbound_orchestrator import OutboundOrchestrator

    settings = get_settings()
    orch = OutboundOrchestrator(config)
    system_prompt = orch.build_system_prompt()

    # 1. Dial out via Telnyx (existing helper)
    # 2. Connect LiveKit room
    # 3. TTS the greeting: config.greeting
    # 4. Enter STT → Gemini(system_prompt) → TTS loop
    #    - Each STT chunk: orch.append_turn("client", text, timestamp)
    #    - Each Gemini response: orch.append_turn("bot", text, timestamp)
    # 5. Record audio of the whole call to a local temp .wav file
    #    (use existing LiveKit recording or pipe TTS+STT audio to a writer)
    # 6. On hangup or max_duration_seconds:
    #      orch.duration_seconds = (now - call_start).seconds
    #      await orch.finalize(
    #          local_audio_path=temp_path,
    #          bucket_name=settings.gcs_audio_bucket,
    #          webhook_timeout=settings.django_webhook_timeout_seconds,
    #      )
    # 7. Clean up local temp file
```

The placeholder comments above must be replaced with calls to the actual helpers from `src/media/`, `src/stt/`, `src/llm/`, `src/tts/` that already exist. Read each module to wire them up correctly.

**Concrete substeps** (depend on existing code, adapt as needed):
- For dialing: use `src/telephony/telnyx_handler.py:create_outbound_call` or similar; if it doesn't exist, add one that calls Telnyx Call Control API to dial `phone_number`.
- For STT/TTS: reuse the same clients the inbound flow uses.
- For audio recording: LiveKit supports server-side recording, or you can write each PCM frame to a `wave.open(...)` writer in `src/media/`.

- [ ] **Step 3: Manual smoke test**

Run the bot service and trigger a test call:

```bash
uvicorn src.api.app:create_app --factory --port 8080
# In another terminal:
curl -X POST http://localhost:8080/calls/initiate -H "Content-Type: application/json" -d '{
  "call_id": "test-smoke-1",
  "phone_number": "+56912345678",
  "rendered_prompt": "Eres un bot de prueba. Si el cliente saluda, responde.",
  "greeting": "Hola, soy un test.",
  "output_params": ["respondio"],
  "webhook_url": "http://localhost:9999/dummy"
}'
```

Run a `nc -l 9999` listener to confirm the webhook is sent at the end of the call.

(This task has no unit test for the end-to-end flow — it's an integration smoke test. Unit tests cover each component individually in Tasks 4–6.)

- [ ] **Step 4: Commit**

```bash
git add src/orchestrator/call_orchestrator.py src/telephony src/media
git commit -m "feat(orchestrator): run_outbound_call entrypoint driven by OutboundCallConfig"
```

---

## Phase 7 — /calls/initiate Endpoint

### Task 7.1: FastAPI route for /calls/initiate (TDD)

**Files:**
- Create: `src/api/routes/calls.py`
- Modify: `src/api/app.py` (register router)
- Create: `tests/unit/test_calls_endpoint.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_calls_endpoint.py`:
```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_initiate_returns_bot_call_id_and_status(client):
    with patch("src.api.routes.calls.start_outbound_call_task") as mock_task:
        mock_task.return_value = None
        response = client.post(
            "/calls/initiate",
            json={
                "call_id": "abc",
                "phone_number": "+1",
                "rendered_prompt": "Hola",
                "greeting": "Hola",
                "output_params": ["ok"],
                "webhook_url": "http://django/x",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["bot_call_id"] == "abc"
    assert body["status"] == "initiated"
    mock_task.assert_called_once()


def test_initiate_rejects_missing_fields(client):
    response = client.post(
        "/calls/initiate", json={"call_id": "abc", "phone_number": "+1"}
    )
    assert response.status_code == 422  # FastAPI validation error
```

- [ ] **Step 2: Run test (verify fail)**

```bash
pytest tests/unit/test_calls_endpoint.py -v
```
Expected: FAIL with 404 (route not registered).

- [ ] **Step 3: Implement the route**

`src/api/routes/calls.py`:
```python
"""POST /calls/initiate — entry point for outbound calls triggered by Django."""

import asyncio

import structlog
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from src.orchestrator.outbound_orchestrator import OutboundCallConfig

logger = structlog.get_logger(__name__)
router = APIRouter()


class CallInitiateRequest(BaseModel):
    call_id: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=3)
    rendered_prompt: str
    greeting: str
    output_params: list[str] = []
    webhook_url: str


class CallInitiateResponse(BaseModel):
    bot_call_id: str
    status: str


def start_outbound_call_task(config: OutboundCallConfig) -> None:
    """Schedule the outbound call as a background asyncio task. Lazily imports to avoid circulars."""
    from src.orchestrator.call_orchestrator import run_outbound_call

    asyncio.create_task(run_outbound_call(config))


@router.post("/calls/initiate", response_model=CallInitiateResponse)
async def initiate_call(req: CallInitiateRequest, _bg: BackgroundTasks) -> CallInitiateResponse:
    config = OutboundCallConfig(
        call_id=req.call_id,
        phone_number=req.phone_number,
        rendered_prompt=req.rendered_prompt,
        greeting=req.greeting,
        output_params=req.output_params,
        webhook_url=req.webhook_url,
    )
    logger.info("initiate_call_received", call_id=config.call_id, phone=config.phone_number)
    start_outbound_call_task(config)
    return CallInitiateResponse(bot_call_id=req.call_id, status="initiated")
```

- [ ] **Step 4: Register router in `src/api/app.py`**

In `src/api/app.py`, locate `create_app()` and add:
```python
from src.api.routes.calls import router as calls_router

app.include_router(calls_router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_calls_endpoint.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/calls.py src/api/app.py tests/unit/test_calls_endpoint.py
git commit -m "feat(api): POST /calls/initiate endpoint"
```

---

## Phase 8 — Verification

### Task 8.1: Run full BOT_VOZ test suite

**Files:** none

- [ ] **Step 1: Run all unit tests**

```bash
cd C:\Users\tomas\Desktop\trabajo\botvoz\BOT_VOZ
pytest tests/unit/ -v
```

Expected pass list:
- `test_prompt_builder.py` (3)
- `test_gcs_audio.py` (2)
- `test_django_webhook.py` (2)
- `test_outbound_orchestrator.py` (3)
- `test_calls_endpoint.py` (2)
- Existing tests (`test_audio_utils`, `test_session`, `test_turn_manager`) should still pass.

- [ ] **Step 2: Boot the service and probe `/health`**

```bash
uvicorn src.api.app:create_app --factory --port 8080
# Other terminal:
curl http://localhost:8080/health
```
Expected: 200 OK with health status.

- [ ] **Step 3: Probe `/calls/initiate` with a fake webhook listener**

In one terminal:
```bash
python -c "
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('content-length', 0))
        print('GOT WEBHOOK:', self.rfile.read(length).decode())
        self.send_response(200); self.end_headers()
HTTPServer(('localhost', 9999), H).serve_forever()
"
```

In another:
```bash
curl -X POST http://localhost:8080/calls/initiate -H "Content-Type: application/json" -d '{
  "call_id": "smoke-1",
  "phone_number": "+56900000000",
  "rendered_prompt": "Bot de prueba.",
  "greeting": "Hola.",
  "output_params": [],
  "webhook_url": "http://localhost:9999/"
}'
```
Expected: response `{"bot_call_id": "smoke-1", "status": "initiated"}`.

Note: the actual call won't connect without valid Telnyx credentials, but the request should be accepted and the orchestrator task should start. The webhook will fire only if the call reaches `finalize()`.

- [ ] **Step 4: Commit final fixes**

```bash
git add -A
git commit -m "test: BOT_VOZ unit suite green + smoke test verified" || echo "No changes"
```

---

## Phase 9 — Final Integration with Django

### Task 9.1: End-to-end smoke test (requires both services + real Telnyx)

This task is the joint verification of Plan A + Plan B. It is **manual** — there's no automation here because it depends on real telephony.

- [ ] **Step 1: Bring up the stack**

Open three terminals:

```bash
# Terminal 1: SQL Server + Redis (call-workspace docker-compose, adjust to your env)
cd call-workspace
docker-compose up -d db redis

# Terminal 2: Django + Celery
cd call-workspace
python manage.py migrate
python manage.py runserver 0.0.0.0:8000 &
celery -A config worker --loglevel=info &
celery -A config beat --loglevel=info &

# Terminal 3: BOT_VOZ
cd C:\Users\tomas\Desktop\trabajo\botvoz\BOT_VOZ
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8080
```

- [ ] **Step 2: Seed a Script + Campaign in Django admin**

Visit `http://localhost:8000/admin/`. Create:
- A `Script` named "test-confirm" with prompt `"Hola {{nombre}}. Confirma [[asistencia]]."` and greeting `"Hola {{nombre}}"`.
- A `Campaign` named "Test" linked to that script, `is_active=True`.

- [ ] **Step 3: Trigger one batch call via API**

```bash
curl -X POST http://localhost:8000/api/v1/batch/ \
  -H "Content-Type: application/json" \
  -b "sessionid=<your-session>" \
  -d '{
    "campaign_id": 1,
    "calls": [{"phone_number": "+56912345678", "input_params": {"nombre": "Juan"}}]
  }'
```

(Use a test Telnyx-routable number you own.)

- [ ] **Step 4: Observe**

- Celery logs should show `process_batch_item` running and calling BOT_VOZ.
- BOT_VOZ logs should show `initiate_call_received` and the call attempting to dial.
- After the call ends, BOT_VOZ logs should show `call_finalized` with a `gs://` URL.
- Django webhook receiver logs should show the call data arriving.
- Celery should run `analyze_call` and create a `CallAnalysis` row.
- Visit `http://localhost:8000/calls/` and `http://localhost:8000/batch/1/` to see the result populated.

- [ ] **Step 5: Document any issues found and create follow-up tickets**

If issues are found (e.g., GCS permissions, Telnyx routing, prompt formatting), file them as separate small fix-plans. Do NOT extend this plan with patches — keep the integration tight.

---

## Self-Review Notes

- **Spec coverage:** ✅
  - New `/calls/initiate` endpoint: Task 7.1
  - Gemini 2.0 → 2.5 Pro upgrade: Task 2.1
  - Dynamic prompt with `[[output_params]]` instructions: Task 3.1
  - GCS audio upload on call end: Task 4.1
  - Django webhook callback on hangup: Task 5.1
  - OutboundOrchestrator with transcript collection + finalize: Task 6.1, 6.2
  - End-to-end integration verification: Task 9.1

- **No placeholders:** Each step has actual code/commands/expected output. Task 6.2 (wiring the real-time pipeline) intentionally leaves implementation details to the engineer because they depend on the precise shape of `src/orchestrator/call_orchestrator.py` and `src/media/*` which only the engineer can inspect during execution — but the substeps are concrete enough to follow.

- **Type consistency:** `OutboundCallConfig` and `OutboundOrchestrator` consistent across 6.1, 7.1. `CallCompletedPayload` consistent across 5.1, 6.1. `build_dynamic_system_prompt` signature consistent between 3.1 and 6.1.
