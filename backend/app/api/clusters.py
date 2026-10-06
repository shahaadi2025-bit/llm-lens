import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Experiment, ExperimentRun, FailureCluster, FailureMode, User
from app.schemas.clusters import ClusterDetail, ClusterOut
from app.services.access import visible
from app.services.clustering import recompute_clusters
from app.services.explain import failure_outs

router = APIRouter(tags=["clusters"])
NOTE = "Clusters group similar-looking incorrect answers. They describe the outputs, not why the model produced them."


async def _members(session: AsyncSession, cluster_id: uuid.UUID, user: User | None, limit: int | None = None) -> list[FailureMode]:
    """Members the viewer may see (an experiment made private after clustering drops out immediately)."""
    stmt = (select(FailureMode).join(ExperimentRun, ExperimentRun.id == FailureMode.run_id)
            .join(Experiment, Experiment.id == ExperimentRun.experiment_id)
            .where(FailureMode.cluster_id == cluster_id, visible(user)).order_by(FailureMode.created_at))
    if limit:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars())


async def _out(session: AsyncSession, fc: FailureCluster, user: User | None) -> ClusterOut | None:
    members = await _members(session, fc.id, user)
    if not members:
        return None
    ids = [m.run_id for m in members]
    demo = bool((await session.execute(select(Experiment.is_demo_data).join(
        ExperimentRun, ExperimentRun.experiment_id == Experiment.id).where(ExperimentRun.id.in_(ids)))).scalars().first())
    return ClusterOut(
        id=fc.id, label=fc.label, size=len(members), method=fc.method, embedding_model=fc.embedding_model,
        error_types=dict(Counter(m.details.get("error_type", "?") for m in members)),
        forms=dict(Counter(m.details.get("group") or "n/a" for m in members)), includes_demo_data=demo, note=NOTE)


async def _scope(session: AsyncSession, user: User | None) -> list[FailureCluster]:
    """A signed-in user's own clustering if they have one, otherwise the shared clustering."""
    if user is not None:
        own = list((await session.execute(select(FailureCluster).where(FailureCluster.owner_id == user.id)
                                          .order_by(FailureCluster.size.desc()))).scalars())
        if own:
            return own
    return list((await session.execute(select(FailureCluster).where(FailureCluster.owner_id.is_(None))
                                       .order_by(FailureCluster.size.desc()))).scalars())


@router.post("/failure-clusters/recompute", response_model=list[ClusterOut])
async def recompute(session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings),
                    user: User | None = Depends(optional_user)) -> list[ClusterOut]:
    outs = [await _out(session, c, user) for c in await recompute_clusters(session, settings, user)]
    return [o for o in outs if o]


@router.get("/failure-clusters", response_model=list[ClusterOut])
async def list_clusters(session: AsyncSession = Depends(get_session),
                        user: User | None = Depends(optional_user)) -> list[ClusterOut]:
    outs = [await _out(session, c, user) for c in await _scope(session, user)]
    return [o for o in outs if o]


@router.get("/failure-clusters/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: uuid.UUID, limit: int = Query(default=100, ge=1, le=500),
                      session: AsyncSession = Depends(get_session), user: User | None = Depends(optional_user)) -> ClusterDetail:
    fc = await session.get(FailureCluster, cluster_id)
    if fc is None or (fc.owner_id is not None and (user is None or fc.owner_id != user.id)):
        raise HTTPException(404, "cluster not found")
    base = await _out(session, fc, user)
    if base is None:
        raise HTTPException(404, "cluster not found")
    members = await _members(session, fc.id, user, limit)
    return ClusterDetail(**base.model_dump(), members=await failure_outs(session, members))
