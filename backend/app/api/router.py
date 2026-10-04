from fastapi import APIRouter

from app.api import (
    analysis,
    auth,
    clusters,
    configs,
    experiments,
    exports,
    failures,
    fingerprints,
    health,
    models,
    notebook,
    reports,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(experiments.router)
api_router.include_router(models.router)
api_router.include_router(analysis.router)
api_router.include_router(failures.router)
api_router.include_router(clusters.router)
api_router.include_router(fingerprints.router)
api_router.include_router(auth.router)
api_router.include_router(configs.router)
api_router.include_router(reports.router)
api_router.include_router(exports.router)
api_router.include_router(notebook.router)
