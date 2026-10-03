import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Experiment, ExperimentRun, FailureCluster, FailureMode
from app.schemas.clusters import ClusterDetail, ClusterOut
from app.services.clustering import recompute_clusters
from app.services.explain import failure_out

router = APIRouter(tags=["clusters"])
NOTE = "Clusters group similar-looking incorrect answers. They describe the outputs, not why the model produced them."


async def _members(session: AsyncSession, cluster_id: uuid.UUID, limit: int | None = None) -> list[FailureMode]:
    stmt = select(FailureMode).where(FailureMode.cluster_id == cluster_id).order_by(FailureMode.created_at)
    if limit:
        stmt = stmt.limit(limit)
    return list((await session.execute(stmt)).scalars())


async def _out(session: AsyncSession, fc: FailureCluster) -> ClusterOut:
    members = await _members(session, fc.id)
    demo = False
    if members:
        ids = [m.run_id for m in members]
        demo = bool((await session.execute(select(Experiment.is_demo_data).join(
            ExperimentRun, ExperimentRun.experiment_id == Experiment.id).where(ExperimentRun.id.in_(ids)))).scalars().first())
    return ClusterOut(
        id=fc.id, label=fc.label, size=fc.size, method=fc.method, embedding_model=fc.embedding_model,
        error_types=dict(Counter(m.details.get("error_type", "?") for m in members)),
        forms=dict(Counter(m.details.get("group") or "n/a" for m in members)), includes_demo_data=demo, note=NOTE)


@router.post("/failure-clusters/recompute", response_model=list[ClusterOut])
async def recompute(session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> list[ClusterOut]:
    return [await _out(session, c) for c in await recompute_clusters(session, settings)]


@router.get("/failure-clusters", response_model=list[ClusterOut])
async def list_clusters(session: AsyncSession = Depends(get_session)) -> list[ClusterOut]:
    cs = (await session.execute(select(FailureCluster).order_by(FailureCluster.size.desc()))).scalars()
    return [await _out(session, c) for c in cs]


@router.get("/failure-clusters/{cluster_id}", response_model=ClusterDetail)
async def get_cluster(cluster_id: uuid.UUID, limit: int = Query(default=100, ge=1, le=500),
                      session: AsyncSession = Depends(get_session)) -> ClusterDetail:
    fc = await session.get(FailureCluster, cluster_id)
    if fc is None:
        raise HTTPException(404, "cluster not found")
    base = await _out(session, fc)
    return ClusterDetail(**base.model_dump(), members=[await failure_out(session, m) for m in await _members(session, fc.id, limit)])
