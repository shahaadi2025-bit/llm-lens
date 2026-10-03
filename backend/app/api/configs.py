import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import required_user
from app.core.db import get_session
from app.experiments.registry import get_experiment_type
from app.experiments.types.base import ConfigError
from app.models import ExperimentConfig, User
from app.schemas.experiment import SavedConfigCreate, SavedConfigOut

router = APIRouter(tags=["configs"])
MAX_CONFIGS_PER_USER = 50


def _out(c: ExperimentConfig) -> SavedConfigOut:
    p = c.config.get("params", {})
    return SavedConfigOut(id=c.id, name=c.name, task_type=c.task_type, temperature=p.get("temperature", 0.0),
                          max_tokens=p.get("max_tokens", 64), seed=p.get("seed", 0), repetitions=p.get("repetitions", 1),
                          config=c.config.get("config", {}), is_public=c.is_public, created_at=c.created_at)


@router.post("/configs", response_model=SavedConfigOut, status_code=201)
async def save_config(body: SavedConfigCreate, session: AsyncSession = Depends(get_session),
                      user: User = Depends(required_user)) -> SavedConfigOut:
    try:
        validated = get_experiment_type(body.task_type).validate_config(body.config)
    except (KeyError, ConfigError) as exc:
        raise HTTPException(400, str(exc)) from exc
    n = (await session.execute(select(func.count()).select_from(ExperimentConfig)
                               .where(ExperimentConfig.owner_id == user.id))).scalar_one()
    if n >= MAX_CONFIGS_PER_USER:
        raise HTTPException(429, f"You can save at most {MAX_CONFIGS_PER_USER} configurations.")
    c = ExperimentConfig(owner_id=user.id, name=body.name, task_type=body.task_type, is_public=body.is_public, config={
        "config": validated, "params": {"temperature": body.temperature, "max_tokens": body.max_tokens,
                                        "seed": body.seed, "repetitions": body.repetitions}})
    session.add(c)
    await session.commit()
    return _out(c)


@router.get("/configs", response_model=list[SavedConfigOut])
async def list_configs(session: AsyncSession = Depends(get_session), user: User = Depends(required_user)) -> list[SavedConfigOut]:
    rows = (await session.execute(select(ExperimentConfig).where(ExperimentConfig.owner_id == user.id)
                                  .order_by(ExperimentConfig.created_at.desc()))).scalars()
    return [_out(c) for c in rows]


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(config_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                        user: User = Depends(required_user)) -> None:
    c = await session.get(ExperimentConfig, config_id)
    if c is None or c.owner_id != user.id:
        raise HTTPException(404, "configuration not found")
    await session.delete(c)
    await session.commit()
