import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from .middleware import LoggingMiddleware
from .routes.health import router as health_router
from .routes.admin import router as admin_router
from .routes.telnyx_webhook import router as telnyx_router
from .routes.test_ui import router as test_ui_router
from .routes.calls import router as calls_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "voicebot_starting",
        environment=settings.environment,
        profile=settings.bot_profile,
    )
    yield
    logger.info("voicebot_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Voice Bot API",
        description="Bot de voz para atención al cliente — GCP + Telnyx + LiveKit",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
    )

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, tags=["Health"])
    app.include_router(admin_router, tags=["Admin"])
    app.include_router(telnyx_router, tags=["Telephony"])
    app.include_router(test_ui_router, tags=["Test UI"])
    app.include_router(calls_router, tags=["Calls"])

    return app


app = create_app()
