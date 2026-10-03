"""Turn evaluated runs into stored metrics with confidence intervals and evidence links.

Every Metric is linked through MetricEvidence to the runs it was computed from, so the UI can always answer
"where does this number come from?" (metric -> runs -> prompts -> responses -> evaluations).
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.experiments.registry import get_experiment_type
from app.models import Evaluation, Experiment, ExperimentRun, Metric, MetricEvidence, ModelVersion, Prompt, Response
from app.models.enums import RunStatus
from app.statistics.proportions import Interval, bootstrap_mean_interval, wilson_interval


@dataclass(frozen=True)
class EvaluatedRow:
    run_id: uuid.UUID
    group: str | None
    block: str | None
    passed: bool
    empty: bool
    latency_ms: float | None


async def load_rows(session: AsyncSession, experiment_id: uuid.UUID, task_type: str) -> list[EvaluatedRow]:
    try:
        etype = get_experiment_type(task_type)
    except KeyError:
        etype = None
    q = (select(ExperimentRun.id, ExperimentRun.latency_ms, Prompt.variant_params, Evaluation.passed, Response.is_empty)
         .join(Prompt, Prompt.run_id == ExperimentRun.id)
         .join(Evaluation, Evaluation.run_id == ExperimentRun.id)
         .join(Response, Response.run_id == ExperimentRun.id)
         .where(ExperimentRun.experiment_id == experiment_id, ExperimentRun.status == RunStatus.SUCCEEDED.value)
         .order_by(ExperimentRun.run_index))
    rows = []
    for run_id, latency, params, passed, empty in (await session.execute(q)).all():
        rows.append(EvaluatedRow(run_id, etype.group_of(params) if etype else None,
                                 etype.block_of(params) if etype else None, bool(passed), bool(empty), latency))
    return rows


async def compute_and_store_metrics(session: AsyncSession, experiment_id: uuid.UUID) -> list[Metric]:
    """Idempotent: replaces this experiment's metrics. Computed from succeeded runs only."""
    exp = await session.get(Experiment, experiment_id)
    if exp is None:
        raise ValueError("experiment not found")
    mv = await session.get(ModelVersion, exp.model_version_id)
    assert mv is not None
    try:
        dimension = get_experiment_type(exp.task_type).fingerprint_dimension
    except KeyError:
        dimension = None
    rows = await load_rows(session, experiment_id, exp.task_type)

    old = list((await session.execute(select(Metric.id).where(Metric.experiment_id == experiment_id))).scalars())
    if old:
        await session.execute(delete(MetricEvidence).where(MetricEvidence.metric_id.in_(old)))
        await session.execute(delete(Metric).where(Metric.id.in_(old)))
    if not rows:
        await session.commit()
        return []

    made: list[tuple[str, str | None, Interval, list[uuid.UUID]]] = []
    made.append(("accuracy", dimension, wilson_interval(sum(r.passed for r in rows), len(rows)), [r.run_id for r in rows]))
    for g in sorted({r.group for r in rows if r.group}):
        sub = [r for r in rows if r.group == g]
        made.append((f"accuracy[{g}]", None, wilson_interval(sum(r.passed for r in sub), len(sub)), [r.run_id for r in sub]))
    made.append(("empty_response_rate", None, wilson_interval(sum(r.empty for r in rows), len(rows)),
                 [r.run_id for r in rows]))
    lat = [r for r in rows if r.latency_ms is not None]
    if len(lat) >= 2:
        made.append(("latency_ms_mean", None, bootstrap_mean_interval([r.latency_ms for r in lat]),  # type: ignore[misc]
                     [r.run_id for r in lat]))

    metrics = []
    for name, dim, iv, run_ids in made:
        m = Metric(experiment_id=experiment_id, model_version_id=mv.id, name=name, dimension=dim, value=iv.estimate,
                   ci_low=iv.low, ci_high=iv.high, ci_level=iv.level, n=iv.n, method=iv.method)
        session.add(m)
        await session.flush()
        session.add_all([MetricEvidence(metric_id=m.id, run_id=rid) for rid in run_ids])
        metrics.append(m)
    await session.commit()
    return metrics
