import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import available_adapters, get_adapter
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
    for a in available_adapters():  # every model this server can run is listed, even before its first experiment
        await ensure_model_version(session, a.get_model_info())
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


class VersionOut(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    model_slug: str
    display_name: str
    version_label: str
    is_mock: bool
    experiment_count: int


@router.get("/model-versions", response_model=list[VersionOut])
async def model_versions(session: AsyncSession = Depends(get_session)) -> list[VersionOut]:
    rows = (await session.execute(select(ModelVersion, LLMModel).join(LLMModel, LLMModel.id == ModelVersion.model_id)
                                  .order_by(LLMModel.slug, ModelVersion.version_label))).all()
    out = []
    for mv, m in rows:
        n = (await session.execute(select(func.count()).select_from(Experiment)
                                   .where(Experiment.model_version_id == mv.id))).scalar_one()
        out.append(VersionOut(id=mv.id, model_id=m.id, model_slug=m.slug, display_name=m.display_name,
                              version_label=mv.version_label, is_mock=m.is_mock, experiment_count=n))
    return out
