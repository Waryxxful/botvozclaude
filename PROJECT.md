# BOT_VOZ — Estado del Proyecto

**Última actualización:** 2026-05-13  
**Rama activa:** `feat/voice-bot-integration`  
**Branch principal:** `master`

---

## Arquitectura general

El proyecto es **dos servidores integrados** que corren en simultáneo:

| Servidor | Puerto | Tecnología | Responsabilidad |
|---|---|---|---|
| **Django (Daphne)** | `8001` | Django 6 + Django Channels | Web UI, API REST, WebSocket del bot |
| **FastAPI** | `8080` | FastAPI + Uvicorn | Webhooks Telnyx, API auxiliar (health, admin) |

```
Navegador → localhost:8001 (Django/Daphne)
  ├── UI con sidebar (base.html + duralux-admin template)
  ├── WS /ws/bot-test/  → consumers.py  → GCP (TTS + STT + Gemini)
  └── REST /api/v1/     → django-ninja  → BD SQLite

Telnyx → localhost:8080 (FastAPI)  [pendiente de probar con URL pública]
  └── POST /webhooks/telnyx → CallOrchestrator
```

---

## Cómo levantar los servidores

```bash
# ── Django (Daphne) ────────────────────────────────────────────────────────
cd BOT_VOZ\call-workspace
py -3.13 -m daphne -b 127.0.0.1 -p 8001 config.asgi:application

# ── FastAPI ────────────────────────────────────────────────────────────────
cd BOT_VOZ
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8080 --reload
```

### Login
- URL: http://localhost:8001
- Usuario: `admin` / Contraseña: `admin123`

---

## Estructura del proyecto

```
BOT_VOZ/
├── src/                    FastAPI app + pipeline de voz
│   ├── api/                FastAPI routes (health, telnyx_webhook, calls, test_ui)
│   ├── tts/                GoogleTTS — acepta speed y pitch
│   ├── llm/                GeminiClient — acepta temperature y max_tokens
│   ├── stt/                STT factory (Google/Deepgram)
│   ├── session/            SessionState (historial de conversación)
│   └── orchestrator/       CallOrchestrator para llamadas Telnyx reales
│
├── config/
│   ├── settings.py         Pydantic settings (carga .env, SSL bundle)
│   ├── bot_config.py       load_bot_profile(), get_default_profile()
│   └── bot_profiles/       YAMLs de perfiles del bot
│
├── call-workspace/         Django app (UI + API REST)
│   ├── apps/
│   │   ├── accounts/       Custom User
│   │   ├── campaigns/      Campaña (FK a Script)
│   │   ├── calls/          Call + CallAnalysis + consumers.py (WS bot)
│   │   ├── scripts/        Script + AgentGlobalConfig + config_resolver
│   │   ├── batch/          BatchJob + BatchCallItem
│   │   └── docs/           Página de documentación para developers
│   ├── api/v1/             django-ninja REST API
│   ├── config/
│   │   ├── settings/       Django settings (base.py, dev.py)
│   │   │   └── __init__.py SHIM: expone get_settings() de BOT_VOZ
│   │   ├── bot_config.py   SHIM: re-exporta desde BOT_VOZ
│   │   ├── bot_profiles/   SHIM: re-exporta BotProfileSchema desde BOT_VOZ
│   │   └── asgi.py         Django Channels routing
│   └── templates/          Todas las plantillas (extienden base.html)
│
└── docs/superpowers/       Specs y planes de implementación
    ├── specs/
    └── plans/
```

---

## Problema de shims de configuración

Django corre desde `call-workspace/` — esto hace que `config.*` resuelva al paquete Django en vez de al módulo FastAPI. Se resuelve con 3 shims:

| Archivo | Qué hace |
|---|---|
| `call-workspace/config/settings/__init__.py` | Expone `get_settings()` cargando `BOT_VOZ/config/settings.py` por ruta absoluta. También carga `.env` desde BOT_VOZ y resuelve `GOOGLE_APPLICATION_CREDENTIALS` a ruta absoluta. |
| `call-workspace/config/bot_config.py` | Re-implementa `load_bot_profile()` y `get_default_profile()` apuntando a los YAMLs de BOT_VOZ. |
| `call-workspace/config/bot_profiles/schema.py` | Carga `BotProfileSchema` desde `BOT_VOZ/config/bot_profiles/schema.py` via `importlib`. |

> **Si aparece `ModuleNotFoundError` con `config.*`:** verificar que el shim correspondiente existe y que la ruta calculada con `.parent.parent.parent.parent` llega a `BOT_VOZ/`.

---

## Base de datos

**Local:** SQLite en `call-workspace/test.sqlite3`  
**Producción (pendiente):** SQL Server — cambiar `ENGINE` en `base.py`

### Modelos principales

| Modelo | App | Campos clave |
|---|---|---|
| `Script` | scripts | `prompt_template`, `greeting`, `input_params`, `output_params`, + 7 campos config (tts_voice, tts_speed, tts_pitch, llm_temperature, llm_max_tokens, vad_silence_ms, max_call_duration_seconds) |
| `AgentGlobalConfig` | scripts | Singleton — defaults globales para todos los scripts |
| `Campaign` | campaigns | FK → Script |
| `BatchJob` | batch | FK → Campaign, `source` (csv/api), progress counters |
| `BatchCallItem` | batch | FK → BatchJob, `phone_number`, `input_params` (JSON) |
| `Call` | calls | UUID PK, FK → Campaign, `status`, `audio_gcs_url` |
| `CallAnalysis` | calls | OneToOne → Call, `output_data` (JSON), `compliance_score` |

### Migrar en SQLite local
```bash
cd call-workspace
py -3.13 manage.py migrate
py -3.13 manage.py createsuperuser
```

---

## Sintaxis de scripts

```
Saludo:   "Hola {{nombre}} desde {{consecionario}}"
Prompt:   "Confirmar {{fecha_agenda}} ... [[confirmacion]]"
          ## comentario interno ##

input_params  → [nombre, consecionario, fecha_agenda]   (del greeting + prompt)
output_params → [confirmacion]                           (solo del prompt)
```

- `{{var}}` = entrada, se reemplaza antes de llamar
- `[[var]]` = salida, el bot la captura y queda en `CallAnalysis.output_data`
- `## ##` = comentario, solo visible al editar el script

---

## Páginas UI disponibles

| URL | Descripción |
|---|---|
| `/calls/dashboard/` | Dashboard con KPIs |
| `/calls/bot-test/?script_id=N` | Probar bot con micrófono del PC |
| `/scripts/` | Lista de scripts |
| `/scripts/nuevo/` | Crear script (3 tabs: Contenido / Voz / Comportamiento) |
| `/scripts/settings/agente/` | Configuración global del agente |
| `/batch/` | Lista de lotes |
| `/batch/nuevo/` | Subir CSV para lote |
| `/campaigns/` | Campañas |
| `/docs/developers/` | Documentación API para desarrolladores |
| `/api/v1/docs` | Swagger interactivo |
| `/admin/` | Django Admin |

---

## API REST (django-ninja)

Autenticación: sesión Django (cookie `sessionid` + header `X-CSRFToken`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/v1/campaigns/` | Listar campañas |
| POST | `/api/v1/campaigns/` | Crear campaña |
| PUT | `/api/v1/campaigns/{id}/` | Actualizar campaña |
| POST | `/api/v1/batch/` | Crear lote de llamadas |
| GET | `/api/v1/calls/` | Listar llamadas (filtros: campaign_id, status) |
| GET | `/api/v1/calls/{uuid}/` | Detalle de llamada |
| GET | `/api/v1/calls/{uuid}/analysis/` | Análisis LLM |
| GET | `/scripts/api/{id}/json/` | Datos del script (input/output params) |

---

## Tests

```bash
# Django (call-workspace)
cd call-workspace
py -3.13 -m pytest tests/ -v          # 9 tests — parsers + config_resolver

# BOT_VOZ (FastAPI)
cd BOT_VOZ
py -3.13 -m pytest tests/unit/ -v -m "not integration"   # sin GCP
```

---

## Estado por componente

### ✅ Funcionando

| Componente | Notas |
|---|---|
| Django UI completa | Scripts, batch, campaigns, bot test, docs |
| Bot de prueba (micrófono PC) | WebSocket vía Django Channels en `/ws/bot-test/` |
| Google TTS (Neural2) | Voces mujer/hombre, speed y pitch configurables por script |
| Google STT v2 | Streaming, `es-US` |
| Gemini via Vertex AI | Streaming, temperature y max_tokens configurables |
| API REST django-ninja | Batch, campaigns, calls |
| Configuración por script | tts_voice, tts_speed, llm_temperature, etc. con fallback a global |
| Variables `{{}}` en saludo | Parser combina inputs de greeting + prompt |
| Documentación developers | `/docs/developers/` con snippets Python completos |

### ⚠️ Pendiente / Incompleto

| Componente | Estado | Qué falta |
|---|---|---|
| **Telefonía Telnyx** | ❌ No probado | Ver sección "Qué falta para telefonía" |
| **Celery + Redis** | ❌ No corriendo en local | Batch usa `.delay()` — sin worker las llamadas no se procesan |
| **Análisis post-llamada** | ⚠️ Código existe (`analyze_call` task) | Depende de Celery worker |
| **Audio en GCS** | ⚠️ Código existe | Necesita bucket GCS configurado |
| **SQL Server** | ❌ Solo SQLite local | Cambiar `ENGINE` en `base.py` + instalar `mssql` driver |
| **webrtcvad en Windows** | ❌ No disponible | Necesita Visual Studio Build Tools (solo afecta ruta Telnyx) |
| **Dashboard KPIs** | ⚠️ Vista existe | Sin datos reales hasta tener llamadas procesadas |

---

## Qué falta para hacer llamadas telefónicas reales (Telnyx)

| # | Qué falta | Cómo resolverlo |
|---|-----------|-----------------|
| 1 | **URL pública** | `ngrok http 8080` → copiar URL HTTPS |
| 2 | **Telnyx Media Streaming** | Portal Telnyx → SIP Connection → Media Streaming → activar con URL ngrok |
| 3 | **Pub/Sub topic** | `gcloud pubsub topics create voice-bot-call-events` |
| 4 | **webrtcvad** | Instalar Visual Studio Build Tools, o usar Docker |
| 5 | **Celery worker** | `celery -A config.celery worker -l info` (requiere Redis) |

Variables de `.env` requeridas: `TELNYX_API_KEY`, `TELNYX_PUBLIC_KEY`, `TELNYX_SIP_CONNECTION_ID` (ya presentes).

---

## Notas técnicas importantes

### SSL / Antivirus (Windows)
`config/settings.py` mezcla certifi + Windows trust store. Necesario con Avast u otros proxies corporativos que interceptan HTTPS. Sin esto, gRPC de GCP falla. En Cloud Run no tiene efecto.

### Credenciales GCP
El shim `call-workspace/config/settings/__init__.py` convierte `./botvozcrmintouch-189b7029fad8.json` (ruta relativa) a ruta absoluta basada en `BOT_VOZ/`. Esto es necesario porque Daphne corre desde `call-workspace/` no desde `BOT_VOZ/`.

### Daphne vs runserver
El servidor Django **debe correr con Daphne** (no `manage.py runserver`) para que el WebSocket del bot funcione. `runserver` no soporta ASGI con Django Channels correctamente.

### BotProfileSchema — campo `description`
Es requerido (sin default). Al crear perfiles en `consumers.py` siempre pasar `description=script.description or ""`.

---

## Deploy en GCP (Cloud Run)

El `cloudbuild.yaml` existe para FastAPI. El Django aún no tiene pipeline de deploy. Para producción se necesitaría:
1. Containerizar el Django con Daphne
2. Configurar SQL Server o Cloud SQL
3. Configurar Redis para Celery
4. Hacer el deploy coordinado de ambos servicios

---

## Archivos importantes a no perder

| Archivo | Descripción |
|---|---|
| `botvozcrmintouch-189b7029fad8.json` | Credenciales GCP — en `.gitignore`, nunca commitear |
| `.env` | Variables de entorno — en `.gitignore` |
| `call-workspace/test.sqlite3` | Base de datos local — en `.gitignore` |
| `docs/superpowers/specs/` | Specs de diseño de features |
| `docs/superpowers/plans/` | Planes de implementación |
