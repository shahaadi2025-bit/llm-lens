from fastapi import APIRouter

from app.api import experiments, health, models

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(experiments.router)
api_router.include_router(models.router)
