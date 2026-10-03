import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user
from app.api.experiments import _summaries, build_run_outs
from app.core.db import get_session
from app.models import (
    Experiment,
    ExperimentRun,
    FailureCluster,
    FailureMode,
    LLMModel,
    Metric,
    MetricEvidence,
    ModelVersion,
    User,
)
from app.models.enums import ExperimentStatus
from app.schemas.analysis import (
    AnalysisOut,
    DashboardOut,
    GroupStat,
    MetricEvidenceOut,
    MetricOut,
    StatementOut,
)
from app.services.access import get_visible, visible
from app.services.metrics import compute_and_store_metrics, load_rows
from app.statistics.sensitivity import analyse

router = APIRouter(tags=["analysis"])

LIMITATIONS = [
    "Black-box observation: results describe this model's outputs on these prompts, not its internal mechanisms.",
    "Intervals are Wilson 95% for proportions. Small samples give wide intervals; read n before reading the number.",
    "Cochran's Q is exploratory here: no correction for multiple comparisons, and it assumes problems are independent.",
]


async def _metric_out(session: AsyncSession, m: Metric) -> MetricOut:
    count = (await session.execute(select(func.count()).select_from(MetricEvidence)
                                   .where(MetricEvidence.metric_id == m.id))).scalar_one()
    exp = await session.get(Experiment, m.experiment_id)
    return MetricOut(id=m.id, experiment_id=m.experiment_id, name=m.name, dimension=m.dimension, value=m.value,
                     ci_low=m.ci_low, ci_high=m.ci_high, ci_level=m.ci_level, n=m.n, method=m.method,
                     evidence_runs=count, is_demo_data=bool(exp and exp.is_demo_data))


@router.get("/experiments/{experiment_id}/metrics", response_model=list[MetricOut])
async def experiment_metrics(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                             user: User | None = Depends(optional_user)) -> list[MetricOut]:
    await get_visible(session, experiment_id, user)
    ms = list((await session.execute(select(Metric).where(Metric.experiment_id == experiment_id)
                                     .order_by(Metric.name))).scalars())
    if not ms:  # e.g. finished before metrics existed: compute lazily, idempotently
        ms = await compute_and_store_metrics(session, experiment_id)
    return [await _metric_out(session, m) for m in ms]


@router.get("/metrics/{metric_id}/evidence", response_model=MetricEvidenceOut)
async def metric_evidence(metric_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                          user: User | None = Depends(optional_user)) -> MetricEvidenceOut:
    m = await session.get(Metric, metric_id)
    if m is None:
        raise HTTPException(404, "metric not found")
    await get_visible(session, m.experiment_id, user)  # 404 if the experiment is private to someone else
    run_ids = list((await session.execute(select(MetricEvidence.run_id).where(MetricEvidence.metric_id == m.id))).scalars())
    runs = list((await session.execute(select(ExperimentRun).where(ExperimentRun.id.in_(run_ids))
                                       .order_by(ExperimentRun.run_index))).scalars())
    return MetricEvidenceOut(metric=await _metric_out(session, m), runs=await build_run_outs(session, runs))


@router.get("/experiments/{experiment_id}/analysis", response_model=AnalysisOut)
async def experiment_analysis(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                              user: User | None = Depends(optional_user)) -> AnalysisOut:
    exp = await get_visible(session, experiment_id, user)
    rows = [(r.group, r.block, r.passed) for r in await load_rows(session, experiment_id, exp.task_type)
            if r.group and r.block]
    res = analyse(rows)
    return AnalysisOut(
        experiment_id=exp.id, is_demo_data=exp.is_demo_data, method="wilson-95 per form; cochran-q across forms",
        groups=[GroupStat(group=g, accuracy=i.estimate, ci_low=i.low, ci_high=i.high, n=i.n) for g, i in res.groups.items()],
        n_blocks=res.n_blocks, cochran_q=res.cochran_q, cochran_df=res.cochran_df, cochran_p=res.cochran_p,
        best=res.best, worst=res.worst, spread=res.spread, cohens_h=res.cohens_h,
        statements=[StatementOut(text=s.text, evidence_level=s.evidence_level) for s in res.statements],
        limitations=LIMITATIONS)


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(session: AsyncSession = Depends(get_session), user: User | None = Depends(optional_user)) -> DashboardOut:
    vis = visible(user)
    total = (await session.execute(select(func.count()).select_from(Experiment).where(vis))).scalar_one()
    completed = (await session.execute(select(func.count()).select_from(Experiment).where(
        vis, Experiment.status == ExperimentStatus.COMPLETED.value))).scalar_one()
    models = (await session.execute(select(func.count(func.distinct(LLMModel.id))).select_from(Experiment)
                                    .join(ModelVersion, ModelVersion.id == Experiment.model_version_id)
                                    .join(LLMModel, LLMModel.id == ModelVersion.model_id).where(vis))).scalar_one()
    flagged = (await session.execute(
        select(FailureMode.run_id, FailureMode.label, FailureMode.details)
        .join(ExperimentRun, ExperimentRun.id == FailureMode.run_id)
        .join(Experiment, Experiment.id == ExperimentRun.experiment_id).where(vis))).all()
    # Count distinct runs, not detector rows. Statistical outliers count only when >= 2 methods agree: a single
    # method (Isolation Forest especially) flags a fixed fraction of any data set by construction.
    anomalies = len({r for r, label, d in flagged if label == "representation_sensitivity" or d.get("n_methods", 0) >= 2})
    own = (await session.execute(select(func.count()).select_from(FailureCluster).where(
        FailureCluster.owner_id == user.id))).scalar_one() if user else 0
    shared = (await session.execute(select(func.count()).select_from(FailureCluster).where(
        FailureCluster.owner_id.is_(None)))).scalar_one()
    clusters = own or shared  # a signed-in user's own clustering replaces the shared one
    recent = list((await session.execute(select(Experiment).where(vis).order_by(Experiment.created_at.desc()).limit(5))).scalars())
    demo = (await session.execute(select(func.count()).select_from(Experiment)
                                  .where(vis, Experiment.is_demo_data.is_(True)))).scalar_one()
    return DashboardOut(
        experiments_total=total, experiments_completed=completed, models_tested=models, potential_anomalies=anomalies,
        failure_clusters=clusters, recent=await _summaries(session, recent, user), includes_demo_data=demo > 0,
        notes=[
            "Counts include only experiments you are allowed to see: public ones, shared demo ones and your own.",
            "Potential anomalies are distinct runs flagged by form-sensitivity or by two or more outlier methods; "
            "they are not confirmed failures.",
        ])
