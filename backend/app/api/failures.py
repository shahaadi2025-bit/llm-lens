import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.experiments import _info_from_db, _summaries
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.experiments.followups import FollowUpNotSupported, build_followup
from app.experiments.service import ServiceError, create_experiment
from app.models import Experiment, ExperimentLineage, ExperimentRun, FailureMode, LLMModel, ModelVersion
from app.schemas.experiment import ExperimentOut
from app.schemas.failures import ExplainOut, FailureOut, FollowUpRequest, LineageEdge, LineageNode, LineageOut
from app.services.explain import explain, failure_out, lineage

router = APIRouter(tags=["failures"])


@router.get("/failures", response_model=list[FailureOut])
async def list_failures(
    session: AsyncSession = Depends(get_session), experiment_id: uuid.UUID | None = None, status: str | None = None,
    label: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
) -> list[FailureOut]:
    stmt = select(FailureMode).order_by(FailureMode.created_at.desc()).limit(limit).offset(offset)
    if experiment_id:
        stmt = stmt.join(ExperimentRun, ExperimentRun.id == FailureMode.run_id).where(ExperimentRun.experiment_id == experiment_id)
    if status:
        stmt = stmt.where(FailureMode.status == status)
    if label:
        stmt = stmt.where(FailureMode.label == label)
    return [await failure_out(session, f) for f in (await session.execute(stmt)).scalars()]


@router.get("/failures/{failure_id}/explain", response_model=ExplainOut)
async def explain_failure(failure_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ExplainOut:
    fm = await session.get(FailureMode, failure_id)
    if fm is None:
        raise HTTPException(404, "failure not found")
    return await explain(session, fm)


@router.post("/experiments/{experiment_id}/follow-up", response_model=ExperimentOut, status_code=201)
async def follow_up(experiment_id: uuid.UUID, body: FollowUpRequest, session: AsyncSession = Depends(get_session),
                    settings: Settings = Depends(get_settings)) -> ExperimentOut:
    exp = await session.get(Experiment, experiment_id)
    fm = await session.get(FailureMode, body.failure_id)
    if exp is None or fm is None:
        raise HTTPException(404, "experiment or failure not found")
    run = await session.get(ExperimentRun, fm.run_id)
    if run is None or run.experiment_id != exp.id:
        raise HTTPException(422, "that failure does not belong to this experiment")
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    if mv is None or model is None:
        raise HTTPException(409, "original experiment's model is missing")
    try:
        spec = build_followup(exp, fm, settings)
        child = await create_experiment(session, spec, mv, _info_from_db(model, mv), settings)
    except FollowUpNotSupported as exc:
        raise HTTPException(422, str(exc)) from exc
    except ServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    session.add(ExperimentLineage(parent_experiment_id=exp.id, child_experiment_id=child.id, trigger_run_id=fm.run_id,
                                  relation="follow_up", note=spec.hypothesis))
    await session.commit()
    return (await _summaries(session, [child]))[0]


@router.get("/experiments/{experiment_id}/lineage", response_model=LineageOut)
async def experiment_lineage(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> LineageOut:
    if await session.get(Experiment, experiment_id) is None:
        raise HTTPException(404, "experiment not found")
    ids, edges = await lineage(session, experiment_id)
    nodes = []
    for i in ids:
        e = await session.get(Experiment, i)
        assert e is not None
        n = (await session.execute(select(func.count()).select_from(FailureMode).join(
            ExperimentRun, ExperimentRun.id == FailureMode.run_id).where(ExperimentRun.experiment_id == i))).scalar_one()
        nodes.append(LineageNode(id=e.id, name=e.name, status=e.status, is_current=e.id == experiment_id,
                                 is_demo_data=e.is_demo_data, anomalies=n))
    return LineageOut(nodes=nodes, edges=[LineageEdge(parent=e.parent_experiment_id, child=e.child_experiment_id,
                                                      relation=e.relation, trigger_run_id=e.trigger_run_id, note=e.note)
                                          for e in edges])
