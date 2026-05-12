# BOT_VOZ — Estado del Proyecto

**Última actualización:** 2026-05-12  
**Rama:** master

---

## Estado actual

El pipeline STT → LLM → TTS está **funcionando en local**. Hay una interfaz web de prueba en `http://localhost:8000/test/` que permite probar una conversación de voz completa sin número de teléfono. Lo que falta es conectar la telefonía (Telnyx) para hacer llamadas reales.

---

## Componentes y su estado

### Infraestructura
| Archivo | Estado |
|---------|--------|
| `config/settings.py` | ✅ Funcional — carga `.env`, construye bundle SSL compatible con Avast/proxies corporativos |
| `config/bot_config.py` | ✅ Funcional |
| `config/bot_profiles/default.yaml` | ✅ Funcional — idioma `es-US`, voz `es-US-Neural2-A` |
| `config/bot_profiles/simple_qa.yaml` | ✅ Funcional — perfil activo según `.env` |
| `Dockerfile` | ✅ Listo para Cloud Run (python:3.12-slim) |
| `cloudbuild.yaml` | ✅ Pipeline Cloud Build → Artifact Registry → Cloud Run |
| `requirements.txt` | ✅ Actualizado para Python 3.13 (telnyx quitado, numpy≥2.1, pydantic≥2.10, aiohttp libre, GCP packages actualizados) |

### API (FastAPI)
| Endpoint | Estado |
|----------|--------|
| `GET /health` | ✅ OK |
| `GET /health/readiness` | ✅ OK |
| `GET /test/` | ✅ **UI de prueba vocal** |
| `WS /test/ws` | ✅ **Saludo TTS → escucha → STT → LLM → TTS funciona end-to-end** |
| `POST /webhooks/telnyx` | ✅ Implementado — requiere Telnyx configurado para probar |
| `GET /admin/*` | ⚠️ Stub — devuelve ceros |

### Pipeline de voz (probado y funcionando)
| Componente | Estado |
|------------|--------|
| Google TTS (Neural2, `es-US-Neural2-A`) | ✅ Funciona — autenticado, produce audio |
| Google STT v2 (streaming, `es-US`) | ✅ Funciona |
| Gemini 2.0 Flash via Vertex AI | ✅ Funciona — streaming + function calling |
| VAD (cliente web, client-side) | ✅ Implementado en JS (AudioWorklet) |
| VAD (servidor, webrtcvad) | ⚠️ No disponible en Windows (sin Visual Studio) — solo se usa en la ruta Telnyx |

### Telefonía (pendiente de probar)
| Componente | Estado |
|------------|--------|
| Webhook Telnyx (Ed25519, parsing) | ✅ Código implementado |
| CallOrchestrator (VAD→STT→LLM→TTS en llamada real) | ✅ Código implementado |
| TelnexMediaStreamingClient (WebSocket con Telnyx) | ✅ Código implementado |
| Prueba con número real | ❌ **No probado** — falta configurar Telnyx y URL pública |

### Persistencia
| Componente | Estado |
|------------|--------|
| Firestore (sessiones, transcripciones) | ✅ Código implementado — credenciales GCP OK |
| Pub/Sub (eventos de llamada) | ✅ Código implementado |
| Colecciones Firestore creadas | ⚠️ Se crean al primer write — no inicializadas manualmente |
| Topic Pub/Sub `voice-bot-call-events` | ⚠️ No verificado si existe |

---

## Qué se probó y funcionó

```
✅ google.cloud.texttospeech: sintetizó "hola mundo" → 42 KB PCM16
✅ WebSocket /test/ws: conecta, envía saludo TTS (278 KB audio), espera voz
✅ STT: transcribe audio PCM16 16kHz desde el micrófono del navegador
✅ LLM: Gemini responde en streaming, se concatena correctamente
✅ TTS: sintetiza la respuesta del LLM, el navegador la reproduce
✅ Conversación multi-turno: la sesión mantiene historial correctamente
```

---

## Qué falta para probar con un número de teléfono real

| # | Qué falta | Cómo resolverlo |
|---|-----------|-----------------|
| 1 | **URL pública para webhook** | `ngrok http 8000` → copiar URL HTTPS |
| 2 | **Telnyx Media Streaming activado** | Portal Telnyx → SIP Connection → Media Streaming → activar con la URL de ngrok |
| 3 | **Pub/Sub topic** | `gcloud pubsub topics create voice-bot-call-events` |
| 4 | **webrtcvad en Windows** | Instalar Visual Studio Build Tools (para compilar la extensión C), o usar Docker |
| 5 | **`gcloud` CLI no instalado** | Instalar Google Cloud SDK para poder ejecutar comandos `gcloud` |

> **Nota:** Las variables `TELNYX_API_KEY`, `TELNYX_PUBLIC_KEY`, `TELNYX_SIP_CONNECTION_ID` ya están en el `.env`. Solo falta exponer el servidor públicamente y activar Media Streaming en el portal.

---

## Cómo correr el servidor local

```bash
# Activar entorno (Python 3.13, creado con py -3.13 -m venv .venv)
.venv\Scripts\python.exe -m uvicorn src.api.app:create_app \
  --factory --host 0.0.0.0 --port 8000 \
  --ws-ping-interval 20 --ws-ping-timeout 30

# Prueba vocal en el navegador
# → http://localhost:8000/test/
```

> El servidor requiere que el proceso se inicie desde `BOT_VOZ/` como directorio de trabajo, ya que `GOOGLE_APPLICATION_CREDENTIALS=./botvozcrmintouch-189b7029fad8.json` es una ruta relativa.

---

## Notas técnicas importantes

### Compatibilidad Python 3.13 / Windows

El proyecto fue diseñado para Python 3.12, pero corre en Python 3.13 con estos ajustes ya aplicados:
- `audioop` (eliminado en 3.13) → reemplazado con numpy puro en `src/media/audio_utils.py`
- `webrtcvad` → import opcional (falla silenciosamente si no hay compilador C)
- `numpy==1.26.4` → actualizado a `>=2.1.0`
- `pydantic==2.7.0` → actualizado a `>=2.10.0` (pydantic-core necesita Rust para 3.12 exact, 3.13 tiene wheels)
- `telnyx==2.2.0` → eliminado de requirements (nunca fue importado en el código)

### SSL / Antivirus

`config/settings.py` construye un bundle PEM combinando certifi + el store de Windows. Necesario porque Avast intercepta HTTPS y firma con su propio certificado raíz. Sin esto, gRPC no puede conectarse a ningún servicio de Google. En Cloud Run no tiene efecto (no hay Avast).

### Arquitectura real vs CLAUDE.md

CLAUDE.md menciona LiveKit, pero el código implementado usa Telnyx Media Streaming directamente (WebSocket a `wss://media.telnyx.com`). Las variables `LIVEKIT_*` en `.env.example` son un vestigio.

```
Telnyx PSTN → POST /webhooks/telnyx
  → CallOrchestrator (asyncio task)
  → TelnexMediaStreamingClient (WebSocket directo a Telnyx)
  → VAD (webrtcvad) → STT → LLM → TTS → audio de vuelta
```

---

## Tests

```bash
# Unit tests (sin GCP):
.venv/Scripts/python.exe -m pytest tests/unit/ -v

# Integration tests (requieren GCP real):
.venv/Scripts/python.exe -m pytest tests/integration/ -m integration
```

Los unit tests cubren `audio_utils`, `session_state` y `turn_manager`. Están pendientes de actualizar para los cambios de numpy en audio_utils (reemplazo de audioop).

---

## Archivos de limpieza pendiente

- `requirements_temp.txt` — archivo temporal, se puede borrar
- `call-workspace/` — directorio clonado externamente, no es parte del proyecto
