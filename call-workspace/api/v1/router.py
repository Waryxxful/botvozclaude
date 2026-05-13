from ninja import NinjaAPI
from ninja.security import django_auth

from .batch import router as batch_router
from .calls import router as calls_router
from .campaigns import router as campaigns_router
from .processing import router as processing_router
from .webhook import router as webhook_router
from .telephony import router as telephony_router
from .health import router as health_router

api = NinjaAPI(
    auth=django_auth,
    title="Voice Bot API",
    version="2.0.0",
    description="""
API unificada del Voice Bot CRM. Gestión de campañas, lotes de llamadas, telefonía Telnyx y análisis.

**Autenticación:** sesión Django — incluir cookie `sessionid` y header `X-CSRFToken`.
Los endpoints `/health/*` y `/webhooks/telnyx` son públicos (sin auth).
    """,
    urls_namespace="api",
)

# Datos (con auth)
api.add_router("/calls", webhook_router, tags=["Calls"])
api.add_router("/calls/", calls_router, tags=["Calls"])
api.add_router("/campaigns/", campaigns_router, tags=["Campaigns"])
api.add_router("/processing/", processing_router, tags=["Processing"])
api.add_router("/batch", batch_router, tags=["Batch"])

# Telefonía + admin (con auth, excepto webhook)
api.add_router("/", telephony_router, tags=["Telephony"])

# Health (sin auth)
api.add_router("/", health_router, tags=["Health"])
