from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_VERSION, Settings, get_settings
from app.core.db import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])

MOCK_NOTICE = (
    "MOCK mode: model outputs are deterministic placeholders, not real LLM behavior. "
    "Nothing produced in this mode is experimental evidence."
)


@router.get("/health", response_model=HealthResponse)
async def health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    db_state: Literal["ok", "unreachable"]
    try:
        await session.execute(text("SELECT 1"))
        db_state = "ok"
    except Exception:  # noqa: BLE001 - health must never raise
        db_state = "unreachable"
    return HealthResponse(
        status="ok" if db_state == "ok" else "degraded",
        version=APP_VERSION,
        environment=settings.app_env,
        database=db_state,
        model_provider=settings.model_provider,
        model_name=settings.model_name,
        mock_mode=settings.is_mock,
        public_demo_mode=settings.public_demo_mode,
        notice=MOCK_NOTICE if settings.is_mock else None,
    )
