import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user
from app.api.deps import adapter_provider, get_adapter, get_engine
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.experiments.engine import EngineError, ExperimentEngine, ModelUnavailable
from app.experiments.registry import list_experiment_types
from app.experiments.service import ServiceError, clone_experiment, create_experiment, ensure_model_version
from app.models import Evaluation, Experiment, ExperimentRun, LLMModel, ModelVersion, Prompt, Response, User
from app.models.enums import ExperimentStatus, RunStatus
from app.schemas.experiment import (
    EvaluationOut,
    ExperimentCreate,
    ExperimentDetail,
    ExperimentOut,
    ExperimentTypeOut,
    RunCounts,
    RunOut,
    VisibilityUpdate,
)
from app.services.access import get_modifiable, get_visible, require_write_identity, visible
from app.services.adapters.base import ModelAdapter, ModelInfo

router = APIRouter(tags=["experiments"])
MOCK_NOTICE = "DEMO / MOCK DATA: produced by a deterministic mock model. Not real LLM behavior; not evidence."


def _http(exc: Exception) -> HTTPException:
    return HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))


async def _counts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, RunCounts]:
    out = {i: RunCounts() for i in ids}
    if not ids:
        return out
    rows = (await session.execute(
        select(ExperimentRun.experiment_id, ExperimentRun.status, func.count())
        .where(ExperimentRun.experiment_id.in_(ids)).group_by(ExperimentRun.experiment_id, ExperimentRun.status)
    )).all()
    for exp_id, status, n in rows:
        c = out[exp_id]
        c.total += n
        setattr(c, status, getattr(c, status) + n)
    passed = (await session.execute(
        select(ExperimentRun.experiment_id, func.count()).join(Evaluation, Evaluation.run_id == ExperimentRun.id)
        .where(ExperimentRun.experiment_id.in_(ids), Evaluation.passed.is_(True),
               ExperimentRun.status == RunStatus.SUCCEEDED.value).group_by(ExperimentRun.experiment_id))).all()
    for exp_id, n in passed:
        out[exp_id].passed = n
    return out


async def _summaries(session: AsyncSession, exps: list[Experiment], user: User | None = None) -> list[ExperimentOut]:
    counts = await _counts(session, [e.id for e in exps])
    result = []
    for e in exps:
        mv = await session.get(ModelVersion, e.model_version_id)
        model = await session.get(LLMModel, mv.model_id) if mv else None
        result.append(ExperimentOut(
            id=e.id, name=e.name, research_question=e.research_question, hypothesis=e.hypothesis,
            task_type=e.task_type, status=e.status, model_slug=model.slug if model else "?",
            model_version=mv.version_label if mv else "?", is_demo_data=e.is_demo_data, is_public=e.is_public,
            owned_by_me=bool(user and e.owner_id == user.id), evaluator=e.evaluator,
            temperature=e.temperature, max_tokens=e.max_tokens, seed=e.seed, repetitions=e.repetitions,
            created_at=e.created_at, started_at=e.started_at, finished_at=e.finished_at, error=e.error,
            counts=counts[e.id]))
    return result


async def build_run_outs(session: AsyncSession, runs: list[ExperimentRun]) -> list[RunOut]:
    """Join runs with their prompt, response and evaluation (the evidence chain, one row per run)."""
    ids = [r.id for r in runs]
    prompts = {p.run_id: p for p in (await session.execute(select(Prompt).where(Prompt.run_id.in_(ids)))).scalars()}
    responses = {r.run_id: r for r in (await session.execute(select(Response).where(Response.run_id.in_(ids)))).scalars()}
    evals: dict[uuid.UUID, Evaluation] = {}
    for row in (await session.execute(select(Evaluation).where(Evaluation.run_id.in_(ids)))).scalars():
        evals[row.run_id] = row
    out = []
    for r in runs:
        pr, resp, ev = prompts[r.id], responses.get(r.id), evals.get(r.id)
        out.append(RunOut(
            id=r.id, run_index=r.run_index, variant_label=r.variant_label, variant_params=pr.variant_params,
            status=r.status, attempt=r.attempt, seed=r.seed, latency_ms=r.latency_ms, prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens, tokens_estimated=bool(resp and resp.raw.get("tokens_estimated")),
            error=r.error, prompt=pr.text, expected_answer=pr.expected_answer, response=resp.text if resp else None,
            evaluation=EvaluationOut.model_validate(ev) if ev else None))
    return out


async def enforce_creation_limits(session: AsyncSession, user: User | None, settings: Settings) -> None:
    """Auth + public-demo quotas shared by create, clone and follow-up."""
    require_write_identity(user, settings)
    if not settings.public_demo_mode:
        return
    total = (await session.execute(select(func.count()).select_from(Experiment))).scalar_one()
    if total >= settings.public_max_total_experiments:
        raise HTTPException(429, "The public demo has reached its storage limit. Run LLM Lens locally for more.")
    if user is not None:
        mine = (await session.execute(select(func.count()).select_from(Experiment)
                                      .where(Experiment.owner_id == user.id))).scalar_one()
        if mine >= settings.public_max_experiments_per_user:
            raise HTTPException(429, f"Public demo accounts are limited to {settings.public_max_experiments_per_user} experiments.")


def _info_from_db(model: LLMModel, mv: ModelVersion) -> ModelInfo:
    return ModelInfo(slug=model.slug, display_name=model.display_name, provider=model.provider,
                     context_length=model.context_length, version_label=mv.version_label, revision=mv.revision,
                     capabilities=model.capabilities, is_mock=model.is_mock)


@router.get("/experiment-types", response_model=list[ExperimentTypeOut])
async def experiment_types() -> list[ExperimentTypeOut]:
    return [ExperimentTypeOut(task_type=t.task_type, title=t.title, research_question=t.research_question,
                              description=t.description, default_evaluator=t.default_evaluator,
                              default_config=t.default_config) for t in list_experiment_types()]


@router.post("/experiments", response_model=ExperimentOut, status_code=201)
async def create(spec: ExperimentCreate, session: AsyncSession = Depends(get_session),
                 adapter: ModelAdapter = Depends(get_adapter), settings: Settings = Depends(get_settings),
                 user: User | None = Depends(optional_user)) -> ExperimentOut:
    await enforce_creation_limits(session, user, settings)
    if user is None:
        spec.is_public = False  # anonymous sandbox experiments are shared by definition; 'public' is for owned ones
    if spec.model_slug:
        try:
            adapter = adapter_provider(spec.model_slug)
        except ModelUnavailable as exc:
            raise HTTPException(409, str(exc)) from exc
    info = adapter.get_model_info()
    try:
        mv = await ensure_model_version(session, info)
        exp = await create_experiment(session, spec, mv, info, settings, owner_id=user.id if user else None)
    except ServiceError as exc:
        raise _http(exc) from exc
    return (await _summaries(session, [exp], user))[0]


@router.get("/experiments", response_model=list[ExperimentOut])
async def list_experiments(
    session: AsyncSession = Depends(get_session), status: str | None = None, task_type: str | None = None,
    q: str | None = Query(default=None, max_length=100), limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0), user: User | None = Depends(optional_user),
) -> list[ExperimentOut]:
    stmt = select(Experiment).where(visible(user)).order_by(Experiment.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Experiment.status == status)
    if task_type:
        stmt = stmt.where(Experiment.task_type == task_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Experiment.name.ilike(like), Experiment.research_question.ilike(like)))
    return await _summaries(session, list((await session.execute(stmt)).scalars()), user)


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetail)
async def detail(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                 user: User | None = Depends(optional_user)) -> ExperimentDetail:
    exp = await get_visible(session, experiment_id, user)
    summary = (await _summaries(session, [exp], user))[0]
    runs = list((await session.execute(select(ExperimentRun).where(ExperimentRun.experiment_id == exp.id)
                                       .order_by(ExperimentRun.run_index))).scalars())
    run_out = await build_run_outs(session, runs)
    return ExperimentDetail(**summary.model_dump(), config=exp.config, environment=exp.environment,
                            software_version=exp.software_version, runs=run_out,
                            notice=MOCK_NOTICE if exp.is_demo_data else None)


@router.post("/experiments/{experiment_id}/run", response_model=ExperimentOut, status_code=202)
async def run(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
              engine: ExperimentEngine = Depends(get_engine), settings: Settings = Depends(get_settings),
              user: User | None = Depends(optional_user)) -> ExperimentOut:
    exp = await get_modifiable(session, experiment_id, user, settings)
    if settings.public_demo_mode and engine.active_count() >= settings.public_max_concurrent_experiments \
            and not engine.is_active(exp.id):
        raise HTTPException(429, "The public demo is busy running other experiments. Try again in a moment.")
    try:
        await engine.start(exp.id)
    except EngineError as exc:
        raise _http(exc) from exc
    await session.refresh(exp)
    return (await _summaries(session, [exp], user))[0]


@router.post("/experiments/{experiment_id}/cancel", response_model=ExperimentOut, status_code=202)
async def cancel(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                 engine: ExperimentEngine = Depends(get_engine), settings: Settings = Depends(get_settings),
                 user: User | None = Depends(optional_user)) -> ExperimentOut:
    exp = await get_modifiable(session, experiment_id, user, settings)
    if engine.cancel(exp.id):
        await engine.wait(exp.id)
    elif exp.status in (ExperimentStatus.PENDING.value, ExperimentStatus.RUNNING.value):
        exp.status = ExperimentStatus.CANCELLED.value  # pending, or orphaned by a server restart
        await session.commit()
    else:
        raise HTTPException(409, f"experiment is {exp.status}; nothing to cancel")
    await session.refresh(exp)
    return (await _summaries(session, [exp], user))[0]


@router.post("/experiments/{experiment_id}/clone", response_model=ExperimentOut, status_code=201)
async def clone(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                settings: Settings = Depends(get_settings), user: User | None = Depends(optional_user)) -> ExperimentOut:
    exp = await get_visible(session, experiment_id, user)  # anyone who can see it may clone it; the clone is theirs
    await enforce_creation_limits(session, user, settings)
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    if mv is None or model is None:
        raise HTTPException(409, "original experiment's model is missing")
    try:
        new = await clone_experiment(session, exp, _info_from_db(model, mv), settings, mv, owner_id=user.id if user else None)
    except ServiceError as exc:
        raise _http(exc) from exc
    return (await _summaries(session, [new], user))[0]




@router.patch("/experiments/{experiment_id}", response_model=ExperimentOut)
async def set_visibility(experiment_id: uuid.UUID, body: VisibilityUpdate, session: AsyncSession = Depends(get_session),
                         user: User | None = Depends(optional_user)) -> ExperimentOut:
    exp = await get_visible(session, experiment_id, user)
    if user is None:
        raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
    if exp.owner_id != user.id:
        raise HTTPException(403, "only the owner can change visibility")
    exp.is_public = body.is_public
    await session.commit()
    return (await _summaries(session, [exp], user))[0]
