from ninja import NinjaAPI
from ninja.security import django_auth

from .calls import router as calls_router
from .campaigns import router as campaigns_router
from .reviews import router as reviews_router
from .processing import router as processing_router

api = NinjaAPI(
    auth=django_auth,
    title="Call Workspace API",
    version="1.0.0",
    description="""
    Esta es la API de acceso y control central para Call Workspace. Permite interactuar programáticamente 
    con las funcionalidades de extracción (FTP), análisis (LLM + Transcripciones), 
    y mantenimiento de registros (Campañas y Llamadas).
    
    ### Consideraciones importantes (Autenticación)
    Todos los endpoints aquí descritos actualmente protegen su acceso mediante **Autenticación por Sesión** 
    (`django_auth`). Esto significa que las peticiones a la API deberán traer en sus headers la Cookie 
    `sessionid` válida generada por el login web del framework principal de Django.
    """,
    urls_namespace="api",
)

api.add_router("/calls/", calls_router, tags=["Calls"])
api.add_router("/campaigns/", campaigns_router, tags=["Campaigns"])
api.add_router("/reviews/", reviews_router, tags=["Reviews"])
api.add_router("/processing/", processing_router, tags=["Processing"])
