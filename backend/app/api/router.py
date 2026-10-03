from fastapi import APIRouter

from app.api import analysis, experiments, health, models

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(experiments.router)
api_router.include_router(models.router)
api_router.include_router(analysis.router)
