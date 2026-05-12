# Call Workspace — Documentación técnica completa

Plataforma Django para análisis automático de llamadas de call center.
Transcribe audio con AssemblyAI, evalúa cumplimiento de scripts con LLM (OpenRouter),
y expone una UI de supervisión con Django templates + HTMX.

---

## Comandos esenciales

```bash
# Levantar el stack completo (primera vez)
docker compose up --build -d

# Levantar sin rebuild
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f web
docker compose logs -f worker

# Detener todo (conserva datos)
docker compose down

# Detener y borrar volúmenes (reset total)
docker compose down -v

# Generar migraciones (tras cambiar modelos)
docker compose run --rm --no-deps --entrypoint="" web python manage.py makemigrations

# Crear superusuario
docker compose exec web python manage.py shell -c \
  "from apps.accounts.models import User; User.objects.create_superuser('admin', 'admin@test.com', 'admin123', role='admin')"

# Encolar una llamada manualmente desde shell
docker compose exec web python manage.py shell -c \
  "from apps.processing.tasks import process_call_task; process_call_task.delay(<call_id>)"
```

---

## Arquitectura

```
┌──────────┐    ┌──────────┐    ┌──────────────────────────────┐
│  Browser │───▶│  Nginx*  │───▶│  Gunicorn (web)  :8000       │
└──────────┘    └──────────┘    │  Django 5 + django-ninja     │
                                └──────────────┬───────────────┘
                                               │
                     ┌─────────────────────────┼─────────────────────┐
                     │                         │                     │
               ┌─────▼──────┐         ┌────────▼───────┐   ┌────────▼───┐
               │ PostgreSQL │         │  Redis (broker)│   │  Celery    │
               │    :5432   │         │    :6379       │   │  worker    │
               └────────────┘         └────────────────┘   │  + beat    │
                                                            └─────┬──────┘
                                                                  │
                                               ┌──────────────────▼──────────────────┐
                                               │  AssemblyAI API  /  OpenRouter API  │
                                               └─────────────────────────────────────┘
```

*Nginx no está configurado en Docker Compose actual; WhiteNoise sirve estáticos desde Gunicorn.

### Servicios Docker

| Servicio | Imagen | Función |
|---|---|---|
| `db` | postgres:16-alpine | Base de datos |
| `redis` | redis:7-alpine | Broker de tareas Celery |
| `web` | (build local) | Django + Gunicorn, corre migraciones al arrancar |
| `worker` | (build local) | Celery worker, procesa transcripción y análisis |
| `beat` | (build local) | Celery beat, dispara el polling FTP cada N segundos |

---

## Configuración — Variables de entorno (`.env`)

Copiar `.env.example` como `.env` y completar los valores.

| Variable | Descripción | Requerida |
|---|---|---|
| `SECRET_KEY` | Clave secreta Django | Sí |
| `DEBUG` | `true` / `false` | No (default false) |
| `ALLOWED_HOSTS` | Hosts permitidos separados por coma | Sí |
| `POSTGRES_DB` | Nombre de la base de datos | No (default `callworkspace`) |
| `POSTGRES_USER` | Usuario PostgreSQL | No (default `postgres`) |
| `POSTGRES_PASSWORD` | Contraseña PostgreSQL | Sí |
| `POSTGRES_HOST` | Host de la BD (en Docker: `db`) | No |
| `REDIS_URL` | URL Redis (en Docker: `redis://redis:6379/0`) | No |
| `ASSEMBLYAI_API_KEY` | Clave API AssemblyAI | Sí |
| `OPENROUTER_API_KEY` | Clave API OpenRouter | Sí |
| `OPENROUTER_MODEL` | Modelo LLM a usar | No (default `meta-llama/llama-3.3-70b-instruct:free`) |
| `FTP_HOST` | Servidor FTP/SFTP | Solo si se usa FTP |
| `FTP_USER` | Usuario FTP | Solo si se usa FTP |
| `FTP_PASSWORD` | Contraseña FTP | Solo si se usa FTP |
| `FTP_PORT` | Puerto FTP | No (default 21) |
| `FTP_USE_SFTP` | `true` para SFTP con paramiko | No (default false) |
| `FTP_BASE_PATH` | Ruta base en el servidor | No (default `/`) |
| `FTP_POLL_INTERVAL` | Segundos entre polls FTP | No (default 900) |

### Modelos OpenRouter

Se recomienda usar modelos `:free` de OpenRouter (~200 req/día gratuitas).
Modelos probados y funcionales: `meta-llama/llama-3.3-70b-instruct:free`

**Advertencia:** No usar `with_structured_output` de LangChain con modelos Llama en OpenRouter —
el método `function_calling` cuelga indefinidamente. El código actual usa el cliente OpenAI
directamente con timeout explícito de 60s y parsing manual de JSON.

---

## Estructura de directorios

```
call-workspace/
├── apps/
│   ├── accounts/       — Custom User con roles (admin / supervisor)
│   ├── campaigns/      — Campaign, Agent + CRUD UI + forms
│   ├── calls/          — Call, Transcription, ComplianceAnalysis + UI completa
│   ├── reviews/        — CallReview (formulario supervisor)
│   └── processing/     — FTPClient, transcription.py, analysis.py, tasks.py
├── api/
│   └── v1/             — django-ninja: router, schemas, endpoints
├── config/
│   ├── settings/
│   │   ├── base.py     — Configuración compartida
│   │   ├── dev.py      — DEBUG=True, hosts libres
│   │   └── prod.py     — DEBUG=False, cookies seguras, HSTS
│   ├── celery.py
│   ├── urls.py
│   └── wsgi.py
├── templates/          — Templates globales (base.html, login, dashboard)
│   ├── calls/
│   ├── campaigns/
│   └── reviews/
├── static/
├── media/              — Archivos de audio subidos (volumen Docker)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
└── requirements.txt
```

---

## Modelos de datos

### `accounts.User` (custom AbstractUser)
| Campo | Tipo | Descripción |
|---|---|---|
| `role` | CharField | `admin` o `supervisor` |
| `is_admin_role` | property | True si role == admin |

### `campaigns.Campaign`
| Campo | Tipo | Descripción |
|---|---|---|
| `name` | CharField | Nombre de la campaña |
| `description` | TextField | Descripción libre |
| `ftp_directory` | CharField | Ruta FTP donde llegan los audios |
| `script_text` | TextField | Script que el agente debe seguir (texto libre) |
| `is_active` | BooleanField | Controla si el polling FTP la procesa |

### `campaigns.Agent`
| Campo | Tipo | Descripción |
|---|---|---|
| `name` | CharField | Nombre del agente |
| `employee_id` | CharField | ID interno (opcional) |
| `campaigns` | M2M → Campaign | Campañas asignadas |
| `is_active` | BooleanField | |

### `calls.Call`
| Campo | Tipo | Descripción |
|---|---|---|
| `campaign` | FK → Campaign | |
| `agent` | FK → Agent (nullable) | |
| `ftp_path` | CharField unique | Ruta FTP original (o `manual/<uuid>/<filename>` para subidas manuales) |
| `audio_file` | FileField | Archivo en `media/audio/` |
| `call_date` | DateField | Fecha de la llamada (opcional) |
| `duration_seconds` | IntegerField | Duración en segundos (opcional) |
| `status` | CharField | `pending` / `transcribing` / `analyzing` / `done` / `error` |
| `error_message` | TextField | Mensaje de error si status=error |
| `processed_at` | DateTimeField | Timestamp de finalización del pipeline |

### `calls.Transcription` (OneToOne → Call)
| Campo | Tipo | Descripción |
|---|---|---|
| `raw_text` | TextField | Texto con etiquetas `Speaker A/B/...` |
| `assemblyai_id` | CharField | ID del transcript en AssemblyAI |

### `calls.ComplianceAnalysis` (OneToOne → Call)
| Campo | Tipo | Descripción |
|---|---|---|
| `script_items` | JSONField | `[{"item": str, "complied": bool}]` |
| `summary` | TextField | Resumen en 2-3 oraciones del LLM |
| `score` | IntegerField | Puntaje 1-10 |
| `llm_model` | CharField | Modelo que generó el análisis |

### `reviews.CallReview` (FK → Call, FK → User)
| Campo | Tipo | Descripción |
|---|---|---|
| `supervisor` | FK → User | Supervisor que hizo la revisión |
| `extra_data` | JSONField | Campos flexibles: actualmente `{notes, score_override}` |
| `reviewed_at` | DateTimeField | Timestamp al guardar |

> **Pendiente:** Los campos exactos de `extra_data` deben definirse con Quintín.
> Se pueden agregar sin migración al ser JSONField.

---

## Pipeline de procesamiento

```
[Audio file] ──▶ process_call_task (Celery)
                       │
                       ├─ Stage 1: TRANSCRIBING
                       │   └─ assemblyai SDK
                       │       ├─ language_code="es"
                       │       ├─ speaker_labels=True
                       │       └─ speech_models=["universal-3-pro", "universal-2"]
                       │   → guarda Transcription.raw_text
                       │
                       └─ Stage 2: ANALYZING
                           └─ openai.OpenAI client → OpenRouter
                               ├─ modelo: OPENROUTER_MODEL
                               ├─ timeout: 60s (httpx.Timeout)
                               ├─ parsing manual con _extract_json()
                               └─ fallback: regex si el modelo añade texto extra
                           → guarda ComplianceAnalysis
```

### Idempotencia del task
`process_call_task` es idempotente: si la `Transcription` o `ComplianceAnalysis` ya
existen, los saltea. Esto permite reprocesar llamadas en error sin duplicar datos.

### Reintentos
- `max_retries=2`, `default_retry_delay=120s`
- Al fallar: guarda el error en `call.error_message`, status → `error`
- El botón "Reprocesar" en la UI resetea el status a `pending` y reencola el task

---

## URLs y vistas

### UI principal

| URL | Vista | Descripción |
|---|---|---|
| `/` | redirect | Redirige a `/calls/dashboard/` |
| `/accounts/login/` | Django auth | Login |
| `/accounts/logout/` | Django auth | Logout |
| `/calls/dashboard/` | `calls.dashboard` | Dashboard con métricas y gráficos |
| `/calls/` | `calls.call_list` | Lista filtrable de llamadas |
| `/calls/nueva/` | `calls.upload_call` | Subida manual de audio |
| `/calls/<id>/` | `calls.call_detail` | Detalle: transcripción + checklist + revisión |
| `/calls/<id>/reprocess/` | `calls.reprocess_call` | POST — reencola el task (HTMX) |
| `/calls/<id>/status/` | `calls.call_status_partial` | GET partial — polling de estado (HTMX) |
| `/calls/agentes/<campaign_id>/` | `calls.campaign_agents` | GET partial — opciones de agentes (HTMX) |
| `/campaigns/` | `campaigns.campaign_list` | Lista de campañas con conteo de llamadas |
| `/campaigns/nueva/` | `campaigns.campaign_create` | Crear campaña |
| `/campaigns/<id>/editar/` | `campaigns.campaign_edit` | Editar campaña |
| `/campaigns/<id>/toggle/` | `campaigns.campaign_toggle` | POST — toggle activa/inactiva (HTMX) |
| `/campaigns/agentes/` | `campaigns.agent_list` | Lista de agentes |
| `/campaigns/agentes/nuevo/` | `campaigns.agent_create` | Crear agente |
| `/campaigns/agentes/<id>/editar/` | `campaigns.agent_edit` | Editar agente |
| `/reviews/<call_id>/` | `reviews.review_form` | GET/POST formulario revisión supervisor (HTMX) |
| `/admin/` | Django admin | Administración completa |

### REST API (`/api/v1/`)

Autenticación: sesión Django (`django_auth`). Documentación Swagger en `/api/v1/docs`.

| Método | URL | Descripción |
|---|---|---|
| GET | `/api/v1/calls/` | Listar llamadas (filtros: `campaign_id`, `status`) |
| GET | `/api/v1/calls/<id>/` | Detalle de llamada |
| GET | `/api/v1/calls/<id>/analysis/` | Análisis de cumplimiento |
| GET | `/api/v1/campaigns/` | Listar campañas |
| POST | `/api/v1/campaigns/` | Crear campaña |
| PUT | `/api/v1/campaigns/<id>/` | Actualizar campaña |
| POST | `/api/v1/reviews/calls/<id>/` | Crear/actualizar revisión |
| GET | `/api/v1/reviews/calls/<id>/` | Obtener revisión |
| POST | `/api/v1/processing/trigger/` | Disparar poll FTP manual |
| GET | `/api/v1/processing/status/` | Estado de Redis, FTP y modelo LLM |

---

## Frontend — stack y patrones

- **Tailwind CSS** vía CDN (`https://cdn.tailwindcss.com`)
- **HTMX 1.9.12** vía CDN — usado para:
  - Filtros de llamadas sin recargar la página
  - Toggle activa/inactiva de campañas
  - Carga de agentes según campaña seleccionada
  - Polling de estado cada 5s en llamadas en proceso
  - Formulario de revisión del supervisor
- **Chart.js 4.4** vía CDN — dashboard: gráfico de barras + doughnut

### Patrones HTMX usados

```html
<!-- Filtrado reactivo -->
<select hx-get="/calls/" hx-trigger="change" hx-target="#calls-tbody">

<!-- Polling periódico -->
<div hx-get="/calls/<id>/status/" hx-trigger="every 5s" hx-swap="outerHTML">

<!-- Form sin reload -->
<form hx-post="/reviews/<id>/" hx-target="#review-section">

<!-- Toggle con partial -->
<button hx-post="/campaigns/<id>/toggle/" hx-target="#badge-<id>" hx-swap="innerHTML">
```

---

## Archivos estáticos y media

- **Estáticos:** servidos por **WhiteNoise** (middleware en `base.py`).
  `collectstatic` corre automáticamente al arrancar el contenedor `web`.
- **Media (audios):** servidos por `django.views.static.serve` en `config/urls.py`.
  Montado como volumen Docker `media_data` en `/app/media/`.
  Para producción real, colocar detrás de nginx.

---

## Entrypoint del contenedor

`entrypoint.sh` solo corre migraciones y `collectstatic` para el proceso `gunicorn`.
Los contenedores `worker` y `beat` arrancan directamente sus procesos sin tocar la BD.
Esto evita la condición de carrera que ocurría cuando los tres contenedores intentaban
migrar simultáneamente al arrancar.

---

## Consideraciones conocidas

### LangChain + Llama en OpenRouter
`with_structured_output(method="function_calling")` cuelga indefinidamente con modelos
Llama vía OpenRouter. El código usa el cliente `openai.OpenAI` directamente con
`httpx.Timeout(60s)` y parsea el JSON de la respuesta con `_extract_json()`, que:
1. Intenta `json.loads()` directo
2. Elimina backticks de markdown y reintenta
3. Busca el primer bloque `{...}` con regex

### Campo `complied` opcional en ScriptItem
Algunos modelos omiten el campo `complied` en items del JSON. Está definido con
`default=False` en el schema Pydantic para no romper la validación.

### Polling FTP sin servidor
Sin `FTP_HOST` configurado, el beat dispara `poll_ftp_task` cada 15 minutos y falla
con `gaierror` (host no resuelto). El error queda en los logs del worker pero no
afecta el procesamiento manual de llamadas.

### `CallReview.extra_data` — campos pendientes
El formulario de revisión actualmente guarda `{notes, score_override}` en el JSONField.
Los campos definitivos deben definirse con Quintín; al ser JSONField no requieren
migración para agregar nuevos campos.

---

## Dependencias principales

| Paquete | Versión | Uso |
|---|---|---|
| `django` | >=5.1 | Framework web |
| `django-ninja` | >=1.3 | REST API |
| `celery[redis]` | >=5.4 | Cola de tareas asíncronas |
| `psycopg2-binary` | >=2.9 | Conector PostgreSQL |
| `assemblyai` | >=0.33 | SDK transcripción de audio |
| `openai` | >=1.30 | Cliente OpenAI / OpenRouter |
| `httpx` | >=0.27 | HTTP client con timeout para OpenAI |
| `langchain` | >=0.3 | Importado pero no usado en el pipeline crítico |
| `langchain-openai` | >=0.2 | Importado pero no usado en el pipeline crítico |
| `pydantic` | >=2.7 | Validación de schemas LLM |
| `gunicorn` | >=22.0 | Servidor WSGI |
| `whitenoise` | >=6.7 | Servir archivos estáticos en producción |
| `paramiko` | >=3.4 | Cliente SFTP |
| `redis` | >=5.0 | Cliente Redis para checks de estado |
