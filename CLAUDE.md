# CLAUDE.md — Voice Bot

## Stack
- **Lenguaje:** Python 3.12 + asyncio
- **Framework web:** FastAPI 0.115 + Uvicorn
- **Telefonía:** Telnyx (PSTN via webhooks)
- **Media server:** LiveKit (audio en tiempo real)
- **STT:** Google Cloud Speech-to-Text v2 (streaming) / Deepgram Nova-2 (baja latencia)
- **TTS:** Google Cloud Text-to-Speech (voces Neural2 en español)
- **LLM:** Gemini 2.0 Flash via Vertex AI (streaming + function calling)
- **Persistencia:** Firestore (sesiones, transcripciones, clientes)
- **Eventos:** Pub/Sub (`voice-bot-call-events`)
- **Observabilidad:** structlog + Prometheus
- **Deploy:** Cloud Run (GCP) via `cloudbuild.yaml`

## Estructura del proyecto

```
BOT_VOZ/
├── src/
│   ├── api/             FastAPI app, middleware, routes (health, admin, telnyx_webhook)
│   ├── orchestrator/    CallOrchestrator (un task asyncio por llamada), EventBus, pipeline
│   ├── session/         SessionManager, TurnManager
│   ├── media/           LiveKitClient, VADProcessor, audio_utils (mulaw→PCM16)
│   ├── stt/             Clientes STT (Google/Deepgram)
│   ├── tts/             GoogleTTS
│   ├── llm/             Cliente Gemini Vertex AI
│   ├── persistence/     Firestore, PubSub publisher
│   └── telephony/       Telnyx webhook handler
├── config/
│   ├── settings.py      Pydantic Settings (desde .env)
│   ├── bot_config.py    load_bot_profile() — lee YAMLs
│   └── bot_profiles/
│       ├── schema.py    BotProfileSchema (Pydantic)
│       └── default.yaml Perfil de bot por defecto
├── tests/
│   ├── unit/            Sin servicios GCP (session, turn_manager, audio_utils)
│   └── integration/     Requieren GCP real (marcados @pytest.mark.integration)
└── infra/               Terraform / configs GCP
```

## Flujo de una llamada

```
Telnyx → POST /webhooks/telnyx
  → crea CallOrchestrator (asyncio task)
  → conecta LiveKit room
  → TTS saludo inicial
  → bucle: VAD detecta fin de turno
    → STT transcribe audio
    → LLM genera respuesta (streaming)
    → TTS sintetiza y envía a LiveKit
  → Pub/Sub: publica eventos (call_started, call_ended, etc.)
  → Firestore: guarda sesión + transcripciones
```

## Comandos

```bash
# Desarrollo local
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8080 --reload

# Tests
pytest tests/unit/                          # sin GCP
pytest tests/ -m "not integration"          # sin GCP
pytest tests/integration/ -m integration   # requiere credenciales GCP reales

# Docker local
docker-compose up --build

# Deploy GCP
gcloud builds submit --config cloudbuild.yaml
```

## Variables de entorno (.env)

```bash
# GCP
GCP_PROJECT_ID=
GCP_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json  # solo local

# Telnyx
TELNYX_API_KEY=
TELNYX_PUBLIC_KEY=
TELNYX_SIP_CONNECTION_ID=

# LiveKit
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# Deepgram
DEEPGRAM_API_KEY=

# Bot
BOT_PROFILE=default                        # nombre del YAML en config/bot_profiles/
BOT_DEFAULT_LANGUAGE=es-419
BOT_TTS_VOICE=es-US-Neural2-A

# Firestore collections
FIRESTORE_CALLS_COLLECTION=calls
FIRESTORE_TRANSCRIPTIONS_COLLECTION=transcriptions

# App
APP_PORT=8080
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## Perfiles de bot (config/bot_profiles/)

Un perfil YAML define el comportamiento completo del bot. Campos clave:

```yaml
name: string
system_prompt: |     # instrucciones al LLM
greeting: string     # saludo inicial en TTS
farewell: string     # despedida
guardrails:
  forbidden_topics: []
  max_call_duration_seconds: 600
  require_customer_identification: false
  post_response_validation: true
memory:
  max_history_turns: 20
  include_customer_data: true
tools:
  enabled: [transfer_call, save_customer_data, lookup_customer]
```

**Para agregar un nuevo perfil:** crear `config/bot_profiles/<nombre>.yaml` siguiendo el schema. Activar con `BOT_PROFILE=<nombre>` en `.env`.

## Agregar un nuevo tool (function calling)

1. Definir la función en `src/llm/` con su schema JSON para Gemini
2. Registrar en `tools.enabled` del perfil YAML
3. Implementar el handler en `src/orchestrator/pipeline.py`
4. Agregar test unitario en `tests/unit/`

## Convenciones de código

- Todo async: `async def` + `await` — **nunca** llamadas bloqueantes en el event loop
- Logging: siempre `structlog.get_logger(__name__)` con campos clave-valor (no f-strings en log)
- Config: siempre via `get_settings()` — nunca `os.environ` directo
- Dependencias: `config/settings.py` como única fuente de verdad de variables de entorno
- Type hints en todas las funciones públicas
- Perfiles de bot: cargar con `load_bot_profile()` — nunca acceder a los YAML directamente
- Errores de servicios externos: usar `tenacity` para retries, no loops manuales

## Observabilidad

- Logs estructurados en JSON (structlog) — cada evento con `call_id` como campo
- Métricas Prometheus en `/metrics`
- Eventos de llamada publicados en Pub/Sub para análisis downstream
- En Cloud Run: los logs van automáticamente a Cloud Logging

## Notas importantes

- El `CallOrchestrator` es **stateful por llamada** — un task asyncio por llamada activa
- El `EventBus` es una `asyncio.Queue` interna al orquestador (no distribuida)
- LiveKit maneja el transport de audio — no procesar audio directamente en FastAPI
- Los tests de integración requieren credenciales GCP reales y colecciones Firestore de test
