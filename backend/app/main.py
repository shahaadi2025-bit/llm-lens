from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import APP_VERSION, Settings, get_settings
from app.core.db import dispose_engine
from app.core.security import RateLimitMiddleware, SecurityHeadersMiddleware
from app.core.spa import mount_frontend


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings().assert_production_safe()
    yield
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="LLM Lens API",
        version=APP_VERSION,
        description="Black-Box LLM Behavioral Intelligence Platform",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    if settings.public_demo_mode:
        app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.public_rate_limit_per_minute)
    # Login/register are always throttled (any mode): this is the brute-force defence.
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.auth_rate_limit_per_minute, path_prefix="/api/auth/")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router)
    app.dependency_overrides[get_settings] = lambda: settings
    if settings.frontend_dist:
        mount_frontend(app, settings.frontend_dist)  # must be registered last: it is a catch-all
    return app


app = create_app()
