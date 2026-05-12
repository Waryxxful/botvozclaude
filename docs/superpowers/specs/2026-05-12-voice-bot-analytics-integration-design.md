# Design Spec: Voice Bot + Call Analytics Integration

**Date:** 2026-05-12  
**Status:** Approved  
**Author:** Brainstorming session with Tomas Valenzuela

---

## 1. Overview

Merge two parallel projects into one unified system:

- **BOT_VOZ** (FastAPI + GCP): real-time voice bot that makes and handles calls via Telnyx/LiveKit
- **call-workspace** (Django + PostgreSQL): call analytics platform with compliance scoring and dashboards

The result is a single platform where Django is the control plane (UI, campaign management, script configuration, analytics, dashboard) and BOT_VOZ remains as a dedicated execution microservice for real-time call handling.

Manual audio upload, FTP polling, AssemblyAI, and OpenRouter/Llama are removed entirely. All AI calls use **Gemini 2.5 Flash Pro** on Vertex AI — both during live calls (BOT_VOZ) and for post-call analysis (Django/Celery).

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                DJANGO (control plane)                │
│   SQL Server · Celery · Redis · HTMX · Chart.js     │
│                                                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Scripts  │  │ Campaigns │  │    Dashboard     │  │
│  │ UI editor│  │ Batch/CSV │  │  [[params]] JSON │  │
│  └──────────┘  └─────┬─────┘  └──────────────────┘  │
│                      │ POST /calls/initiate           │
└──────────────────────┼──────────────────────────────┘
                       │                ▲
                       ▼                │ POST /webhook/call-completed
              ┌─────────────────┐       │ (transcript + GCS audio URL)
              │    BOT_VOZ      │───────┘
              │ FastAPI/asyncio │
              │ Telnyx · LiveKit│
              │ Gemini 2.5 Flash│
              │ Google STT/TTS  │
              │ GCS (audio)     │
              └─────────────────┘
```

### Communication contracts

**Django → BOT_VOZ** (`POST /calls/initiate`):
```json
{
  "call_id": "uuid",
  "phone_number": "+56912345678",
  "rendered_prompt": "Eres un asistente... el cliente es Juan Pérez...",
  "greeting": "Hola Juan, lo llamo de In-Touch CRM...",
  "output_params": ["confirmacion", "motivo_no_asistencia", "nueva_fecha"],
  "webhook_url": "https://django-host/api/v1/calls/webhook/"
}
```

**BOT_VOZ → Django** (`POST webhook_url`):
```json
{
  "call_id": "uuid",
  "status": "completed",
  "duration_seconds": 142,
  "audio_gcs_url": "gs://bucket/calls/uuid.wav",
  "transcript": [
    {"role": "bot", "text": "Hola Juan...", "timestamp": 0.0},
    {"role": "client", "text": "Hola, sí...", "timestamp": 3.4}
  ]
}
```

---

## 3. Script Management (`{{}}` / `[[]]` syntax)

### Syntax rules

| Syntax | Role | Behavior |
|--------|------|----------|
| `{{param}}` | Input — injected before call | Replaced with the value from the batch row before the prompt reaches BOT_VOZ. The bot never sees the double braces. |
| `[[param]]` | Output — collected during call | Converted into an explicit instruction appended to the system prompt: *"At the end of the conversation you must have collected: param (type). Set null if not obtained."* The bot reasons about this during the call, and Gemini extracts structured values post-call. |

### Parser

On save, `Script.prompt_template` is scanned with two regexes:
- `\{\{(\w+)\}\}` → `input_params` list
- `\[\[(\w+)\]\]` → `output_params` list

These lists are stored in JSON columns and drive CSV validation and post-call extraction.

### Example script

```
Eres un asistente de llamadas de In-Touch CRM.
Estás llamando a {{nombre}} para confirmar su visita programada para {{fecha_visita}}.

Si el cliente confirma, registra [[confirmacion]].
Si no puede asistir, registra [[motivo_no_asistencia]] y gestiona el reagendamiento anotando [[nueva_fecha]].

Cuando el cliente mencione fechas relativas ("mañana", "el jueves"), calcula la fecha exacta
basándote en que hoy es la fecha actual y confírmala con el cliente antes de cerrar.
```

### UI — Script editor views

- **List**: table of scripts, name, param count, linked campaigns
- **Create/Edit**: textarea for `prompt_template`, greeting field, auto-detected params shown live below editor
- **Preview**: render the prompt with example values to verify substitution before saving

### CSV format for batch calls

The CSV header must contain `phone_number` plus exactly the columns in `Script.input_params`. Validation runs before any call is enqueued.

```csv
phone_number,nombre,fecha_visita
+56912345678,Juan Pérez,martes 13 de mayo a las 14:00
+56987654321,María López,jueves 15 de mayo a las 10:30
```

---

## 4. Data Model (SQL Server)

### New models

```
Script
  id                  PK
  name                VARCHAR(200)
  description         TEXT (nullable)
  prompt_template     TEXT
  input_params        JSON   -- ["nombre", "fecha_visita"]
  output_params       JSON   -- ["confirmacion", "nueva_fecha"]
  created_at          DATETIME
  updated_at          DATETIME

BatchJob
  id                  PK
  campaign            FK → Campaign
  source              VARCHAR(10)  -- "csv" | "api"
  total_calls         INT
  done_calls          INT
  failed_calls        INT
  status              VARCHAR(20)  -- "pending"|"running"|"completed"|"failed"
  created_at          DATETIME

BatchCallItem
  id                  PK
  batch_job           FK → BatchJob
  phone_number        VARCHAR(30)
  input_params        JSON         -- {"nombre": "Juan", "fecha_visita": "..."}
  status              VARCHAR(20)  -- "pending"|"calling"|"done"|"failed"|"retry"
  bot_call_id         VARCHAR(100) -- ID returned by BOT_VOZ on initiate
  error_message       TEXT (nullable)
  created_at          DATETIME
  called_at           DATETIME (nullable)

CallAnalysis
  id                  PK
  call                OneToOne → Call
  output_data         JSON   -- {"confirmacion": true, "nueva_fecha": null, ...}
  summary             TEXT
  compliance_score    INT    -- 1-10
  llm_model           VARCHAR(100)  -- "gemini-2.5-flash-pro"
  created_at          DATETIME
```

### Modified models

```
Campaign (extended)
  + script            FK → Script (nullable)

Call (extended from call-workspace)
  -- removed: ftp_path, audio_file (FileField)
  + batch_item        FK → BatchCallItem (nullable)
  + phone_number      VARCHAR(30)
  + transcript        JSON   -- [{role, text, timestamp}, ...]
  + audio_gcs_url     VARCHAR(500)
  -- status values updated: "pending"|"calling"|"analyzing"|"done"|"error"
```

### Removed models

- `Agent` — the bot is the agent; no human agent tracking needed
- `Transcription` — transcript lives inside `Call.transcript` as JSON
- `ComplianceAnalysis` → replaced by `CallAnalysis`
- `CallReview` — removed in this phase; can be re-added later if needed

---

## 5. Call Execution Flow

```
Django Celery Worker
  1. Dequeue BatchCallItem (status: pending)
  2. Render script: replace all {{params}} with values from input_params
  3. Append [[params]] extraction instruction to rendered prompt
  4. Create Call record (status: calling)
  5. POST /calls/initiate → BOT_VOZ
     - on timeout (30s): mark BatchCallItem as retry (max 2 retries)

BOT_VOZ FastAPI
  6. Receive initiate request, dial via Telnyx
  7. Connect LiveKit room, play TTS greeting
  8. Loop: VAD → Google Cloud STT → Gemini 2.5 Flash Pro → Google Cloud TTS
     - Gemini understands temporal references ("mañana" = specific date)
     - Bot confirms resolved dates with client before closing
  9. Call ends (hangup or max duration)
  10. Upload audio to GCS: gs://bucket/calls/<call_id>.wav
  11. POST webhook to Django with transcript + audio_gcs_url

Django Celery Worker (webhook handler)
  12. Update Call: transcript, audio_gcs_url, duration, status: analyzing
  13. Update BatchCallItem: status: calling → done (or failed)
  14. Enqueue Gemini analysis task

Gemini 2.5 Flash Pro (Vertex AI, via Django)
  15. Input: full transcript + list of expected [[params]]
  16. Output: structured JSON with one key per [[param]], null if not captured
  17. Output: summary (2-3 sentences) + compliance_score (1-10)
  18. Save CallAnalysis to SQL Server
  19. Update Call.status → done
  20. Dashboard reflects new data
```

### Concurrency and error handling

- Celery processes `BatchCallItems` with a configurable inter-call delay (default: 2 seconds) to avoid saturating Telnyx
- BOT_VOZ initiate timeout: 30 seconds → retry; max 2 retries per item
- Webhook timeout guard: Celery Beat checks every 15 minutes for calls stuck in `calling` status for more than 10 minutes → mark as `error`
- Gemini analysis retries: up to 2 retries with 60s delay on failure

---

## 6. BOT_VOZ Changes

### New endpoint

```
POST /calls/initiate
Body: { call_id, phone_number, rendered_prompt, greeting,
        output_params, webhook_url }
Response: { bot_call_id, status: "initiated" }
```

### Modified behavior

- System prompt is now fully provided by Django (no bot profiles YAML at call time)
- LLM upgraded: Gemini 2.0 Flash → **Gemini 2.5 Flash Pro**
- Audio recording: always write call audio to GCS at end of call
- On call end: POST webhook before shutting down the asyncio task

### Preserved behavior

- All real-time pipeline: Telnyx, LiveKit, Google Cloud STT, Google Cloud TTS
- VAD, turn management, session state
- Pub/Sub events (`call_started`, `call_ended`) still published for observability
- Firestore session storage (for debugging/replay)

---

## 7. Django App Structure

```
call-workspace/
├── apps/
│   ├── accounts/        unchanged — user auth, roles
│   ├── scripts/         NEW — Script model, prompt editor, param parser
│   ├── campaigns/       EXTENDED — adds FK to Script, removes FTP fields
│   ├── batch/           NEW — BatchJob, BatchCallItem, CSV upload, progress UI
│   ├── calls/           EXTENDED — webhook receiver, GCS audio, transcript view
│   └── processing/      EXTENDED — replaces AssemblyAI+OpenRouter with Gemini
├── api/v1/
│   ├── batch.py         NEW — POST /batch/ for external automation
│   ├── calls.py         EXTENDED — webhook endpoint
│   └── campaigns.py     EXTENDED
├── config/
│   └── settings/        base.py — SQL Server, Celery, GCP credentials
└── templates/
    ├── scripts/          NEW — list, form, preview
    ├── batch/            NEW — job list, job detail with progress bar
    └── calls/            EXTENDED — transcript view, [[params]] card, audio player
```

---

## 8. Dashboard Views

### Main dashboard

- Total calls, contact rate, average compliance score, active batch jobs (4 KPI cards)
- Bar chart: average score per campaign (Chart.js)
- `[[param]]` distribution panel: for the active campaign's output params, show value frequency (e.g. `confirmacion: Sí 73% / No 24% / N/R 3%`)
- Recent calls table: last 10 completed calls

### Batch job detail

- Real-time progress bar (HTMX polling every 3 seconds)
- Table: phone number, input params, status, extracted `[[params]]`, score
- Export CSV button: all columns including extracted `[[params]]`

### Call detail

- Audio player (GCS signed URL, 1-hour expiry)
- Full transcript with timestamps and role labels (Bot / Client)
- Extracted data card:
  ```json
  {
    "confirmacion": true,
    "nueva_fecha": null,
    "motivo_no_asistencia": null
  }
  ```
- Compliance score + Gemini summary
- "Re-analyze" button: re-queues Gemini extraction without repeating the call

---

## 9. Technology Stack

| Layer | Technology |
|-------|-----------|
| Web framework | Django 5.1 |
| Database | SQL Server (via `mssql-django`) |
| Task queue | Celery 5 + Redis |
| Frontend | Django Templates + HTMX + Chart.js + Tailwind CSS |
| REST API | django-ninja |
| Voice bot | FastAPI + asyncio (BOT_VOZ microservice) |
| Telephony | Telnyx PSTN |
| Media transport | LiveKit |
| STT (real-time) | Google Cloud Speech-to-Text v2 |
| TTS | Google Cloud Text-to-Speech Neural2 |
| LLM (real-time) | Gemini 2.5 Flash Pro — Vertex AI (in BOT_VOZ) |
| LLM (analysis) | Gemini 2.5 Flash Pro — Vertex AI (in Django/Celery) |
| Audio storage | Google Cloud Storage |
| Events | GCP Pub/Sub |
| Deployment | Cloud Run (BOT_VOZ) + Cloud Run or GKE (Django) |

---

## 10. Out of Scope

- Manual audio upload (removed)
- FTP polling (removed)
- Human agent management (removed)
- Supervisor review forms (removed for now, can be re-added)
- Inbound call handling (bot only makes outbound calls in this version)
- Real-time dashboard WebSocket push (HTMX polling is sufficient)
