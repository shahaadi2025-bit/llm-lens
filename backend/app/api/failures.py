import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user
from app.api.experiments import _info_from_db, _summaries, enforce_creation_limits
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.experiments.followups import FollowUpNotSupported, build_followup
from app.experiments.service import ServiceError, create_experiment
from app.models import Experiment, ExperimentLineage, ExperimentRun, FailureMode, LLMModel, ModelVersion, User
from app.schemas.experiment import ExperimentOut
from app.schemas.failures import ExplainOut, FailureOut, FollowUpRequest, LineageEdge, LineageNode, LineageOut
from app.services.access import can_see, get_modifiable, get_visible, visible
from app.services.explain import explain, failure_outs, lineage

router = APIRouter(tags=["failures"])


@router.get("/failures", response_model=list[FailureOut])
async def list_failures(
    session: AsyncSession = Depends(get_session), experiment_id: uuid.UUID | None = None, status: str | None = None,
    label: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    user: User | None = Depends(optional_user),
) -> list[FailureOut]:
    stmt = (select(FailureMode).join(ExperimentRun, ExperimentRun.id == FailureMode.run_id)
            .join(Experiment, Experiment.id == ExperimentRun.experiment_id).where(visible(user))
            .order_by(FailureMode.created_at.desc()).limit(limit).offset(offset))
    if experiment_id:
        stmt = stmt.where(ExperimentRun.experiment_id == experiment_id)
    if status:
        stmt = stmt.where(FailureMode.status == status)
    if label:
        stmt = stmt.where(FailureMode.label == label)
    return await failure_outs(session, list((await session.execute(stmt)).scalars()))


@router.get("/failures/{failure_id}/explain", response_model=ExplainOut)
async def explain_failure(failure_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                          user: User | None = Depends(optional_user)) -> ExplainOut:
    fm = await session.get(FailureMode, failure_id)
    run = await session.get(ExperimentRun, fm.run_id) if fm else None
    if fm is None or run is None:
        raise HTTPException(404, "failure not found")
    await get_visible(session, run.experiment_id, user)
    return await explain(session, fm)


@router.post("/experiments/{experiment_id}/follow-up", response_model=ExperimentOut, status_code=201)
async def follow_up(experiment_id: uuid.UUID, body: FollowUpRequest, session: AsyncSession = Depends(get_session),
                    settings: Settings = Depends(get_settings), user: User | None = Depends(optional_user)) -> ExperimentOut:
    exp = await get_modifiable(session, experiment_id, user, settings)
    fm = await session.get(FailureMode, body.failure_id)
    if fm is None:
        raise HTTPException(404, "experiment or failure not found")
    await enforce_creation_limits(session, user, settings)
    run = await session.get(ExperimentRun, fm.run_id)
    if run is None or run.experiment_id != exp.id:
        raise HTTPException(422, "that failure does not belong to this experiment")
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    if mv is None or model is None:
        raise HTTPException(409, "original experiment's model is missing")
    try:
        spec = build_followup(exp, fm, settings)
        child = await create_experiment(session, spec, mv, _info_from_db(model, mv), settings,
                                        owner_id=user.id if user else None)
    except FollowUpNotSupported as exc:
        raise HTTPException(422, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    session.add(ExperimentLineage(parent_experiment_id=exp.id, child_experiment_id=child.id, trigger_run_id=fm.run_id,
                                  relation="follow_up", note=spec.hypothesis))
    await session.commit()
    return (await _summaries(session, [child], user))[0]


@router.get("/experiments/{experiment_id}/lineage", response_model=LineageOut)
async def experiment_lineage(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                             user: User | None = Depends(optional_user)) -> LineageOut:
    await get_visible(session, experiment_id, user)
    ids, edges = await lineage(session, experiment_id)
    nodes = []
    shown: set[uuid.UUID] = set()
    for i in ids:
        e = await session.get(Experiment, i)
        if e is None or not can_see(e, user):  # never reveal experiments the viewer may not see
            continue
        shown.add(i)
        n = (await session.execute(select(func.count()).select_from(FailureMode).join(
            ExperimentRun, ExperimentRun.id == FailureMode.run_id).where(ExperimentRun.experiment_id == i))).scalar_one()
        nodes.append(LineageNode(id=e.id, name=e.name, status=e.status, is_current=e.id == experiment_id,
                                 is_demo_data=e.is_demo_data, anomalies=n))
    return LineageOut(nodes=nodes, edges=[LineageEdge(parent=e.parent_experiment_id, child=e.child_experiment_id,
                                                      relation=e.relation, trigger_run_id=e.trigger_run_id, note=e.note)
                                          for e in edges if e.parent_experiment_id in shown and e.child_experiment_id in shown])
