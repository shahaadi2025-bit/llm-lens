"""Who may see and change what.

Visibility: an experiment is visible if it is public, owned by the viewer, or anonymous (owner NULL = the shared demo
sandbox). Everything derived from an experiment (metrics, runs, failures, clusters, fingerprints, lineage) must go
through these helpers. Hidden experiments answer 404, not 403, so their existence is not revealed.
Modification: owners only; anonymous sandbox experiments can be changed by anyone the deployment lets write.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import ColumnElement, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Experiment, User


def visible(user: User | None) -> ColumnElement[bool]:
    conds: list[ColumnElement[bool]] = [Experiment.owner_id.is_(None), Experiment.is_public.is_(True)]
    if user is not None:
        conds.append(Experiment.owner_id == user.id)
    return or_(*conds)


def can_see(exp: Experiment, user: User | None) -> bool:
    return exp.owner_id is None or exp.is_public or (user is not None and exp.owner_id == user.id)


def can_modify(exp: Experiment, user: User | None, settings: Settings) -> bool:
    if user is not None and exp.owner_id == user.id:
        return True
    return exp.owner_id is None and (user is not None or settings.allow_anonymous_writes)


def require_write_identity(user: User | None, settings: Settings) -> None:
    if user is None and not settings.allow_anonymous_writes:
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})


async def get_visible(session: AsyncSession, experiment_id: uuid.UUID, user: User | None) -> Experiment:
    exp = await session.get(Experiment, experiment_id)
    if exp is None or not can_see(exp, user):
        raise HTTPException(404, "experiment not found")
    return exp


async def get_modifiable(session: AsyncSession, experiment_id: uuid.UUID, user: User | None, settings: Settings) -> Experiment:
    exp = await get_visible(session, experiment_id, user)
    if not can_modify(exp, user, settings):
        if user is None:
            raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
        raise HTTPException(403, "only the owner can change this experiment")
    return exp
