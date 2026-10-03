from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unreachable"]
    model_provider: str
    model_name: str
    mock_mode: bool
    public_demo_mode: bool
    notice: str | None = None
