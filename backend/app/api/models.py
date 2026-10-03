import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_adapter
from app.core.db import get_session
from app.core.hardware import detect_hardware
from app.experiments.service import ensure_model_version
from app.models import Experiment, LLMModel, ModelVersion
from app.schemas.experiment import ModelOut
from app.services.adapters.base import ModelAdapter

router = APIRouter(tags=["models"])


async def _to_out(session: AsyncSession, m: LLMModel, configured_slug: str) -> ModelOut:
    version_rows = await session.execute(select(ModelVersion.version_label).where(ModelVersion.model_id == m.id))
    versions = list(version_rows.scalars())
    count = (await session.execute(select(func.count()).select_from(Experiment).join(
        ModelVersion, ModelVersion.id == Experiment.model_version_id).where(ModelVersion.model_id == m.id))).scalar_one()
    return ModelOut(id=m.id, slug=m.slug, display_name=m.display_name, provider=m.provider,
                    context_length=m.context_length, capabilities=m.capabilities, is_mock=m.is_mock,
                    versions=versions, experiment_count=count, configured=m.slug == configured_slug)


@router.get("/models", response_model=list[ModelOut])
async def list_models(session: AsyncSession = Depends(get_session),
                      adapter: ModelAdapter = Depends(get_adapter)) -> list[ModelOut]:
    info = adapter.get_model_info()
    await ensure_model_version(session, info)  # the configured model is always listed
    await session.commit()
    models = (await session.execute(select(LLMModel).order_by(LLMModel.slug))).scalars()
    return [await _to_out(session, m, info.slug) for m in models]


@router.get("/models/{model_id}", response_model=ModelOut)
async def get_model(model_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                    adapter: ModelAdapter = Depends(get_adapter)) -> ModelOut:
    m = await session.get(LLMModel, model_id)
    if m is None:
        raise HTTPException(404, "model not found")
    return await _to_out(session, m, adapter.get_model_info().slug)


@router.get("/system/hardware")
async def hardware() -> dict[str, object]:
    return detect_hardware()
