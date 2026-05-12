"""POST /calls/initiate — entry point for outbound calls triggered by Django."""

import asyncio

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.orchestrator.outbound_orchestrator import OutboundCallConfig

logger = structlog.get_logger(__name__)
router = APIRouter()


class CallInitiateRequest(BaseModel):
    call_id: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=2)
    rendered_prompt: str
    greeting: str
    output_params: list[str] = []
    webhook_url: str


class CallInitiateResponse(BaseModel):
    bot_call_id: str
    status: str


def start_outbound_call_task(config: OutboundCallConfig) -> None:
    """Schedule the outbound call as a background asyncio task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_run_call(config))
    except RuntimeError:
        pass


async def _run_call(config: OutboundCallConfig) -> None:
    """Placeholder: will be wired to the real call pipeline in Phase 6.2."""
    logger.info("outbound_call_started", call_id=config.call_id, phone=config.phone_number)


@router.post("/calls/initiate", response_model=CallInitiateResponse)
async def initiate_call(req: CallInitiateRequest) -> CallInitiateResponse:
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
