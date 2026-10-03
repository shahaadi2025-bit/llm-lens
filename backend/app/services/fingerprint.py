"""Behavioral fingerprint: one honest axis per dimension, each linked to the metrics (and so the runs) behind it.
There is deliberately no single overall score."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.experiments.registry import list_experiment_types
from app.models import Experiment, LLMModel, Metric, ModelVersion
from app.models.enums import ExperimentStatus
from app.schemas.fingerprint import DimensionMetric, DimensionOut, FingerprintOut
from app.statistics.proportions import wilson_interval

DIMENSIONS = {
    "R": "Reasoning", "M": "Mathematics", "F": "Factuality", "C": "Context handling",
    "I": "Instruction following", "H": "Hallucination indicators", "T": "Tool use", "S": "Stability",
}
HOW = {
    "M": "Accuracy on multiplication asked in several equivalent forms (arithmetic representation sensitivity).",
    "S": "Accuracy when the same problems are asked with controlled prompt mutations (prompt sensitivity).",
}
NOT_YET = "No experiment type for this dimension is implemented yet."


async def build_fingerprint(session: AsyncSession, model: LLMModel, version_id: uuid.UUID | None = None) -> FingerprintOut:
    q = (select(Metric, Experiment, ModelVersion).join(Experiment, Experiment.id == Metric.experiment_id)
         .join(ModelVersion, ModelVersion.id == Experiment.model_version_id)
         .where(ModelVersion.model_id == model.id, Metric.name == "accuracy", Metric.dimension.is_not(None),
                Experiment.status == ExperimentStatus.COMPLETED.value))
    version_label = None
    if version_id:
        q = q.where(ModelVersion.id == version_id)
        mv = await session.get(ModelVersion, version_id)
        version_label = mv.version_label if mv else None
    by_dim: dict[str, list[DimensionMetric]] = {}
    for m, e, mv in (await session.execute(q.order_by(Experiment.created_at))).all():
        by_dim.setdefault(m.dimension or "", []).append(DimensionMetric(
            metric_id=m.id, experiment_id=e.id, experiment_name=e.name, version=mv.version_label, value=m.value,
            ci_low=m.ci_low, ci_high=m.ci_high, n=m.n))
    types_by_dim = {t.fingerprint_dimension: t.title for t in list_experiment_types() if t.fingerprint_dimension}

    dims = []
    for code, name in DIMENSIONS.items():
        ms = by_dim.get(code, [])
        if not ms:
            dims.append(DimensionOut(code=code, name=name, measured=False, value=None, ci_low=None, ci_high=None, n=0,
                                     n_experiments=0, method=None, metrics=[],
                                     how_measured=HOW.get(code, NOT_YET)))
            continue
        trials = sum(x.n for x in ms)
        successes = sum(round(x.value * x.n) for x in ms)  # accuracy metrics store value = successes / n
        iv = wilson_interval(successes, trials)
        dims.append(DimensionOut(
            code=code, name=name, measured=True, value=iv.estimate, ci_low=iv.low, ci_high=iv.high, n=trials,
            n_experiments=len(ms), method=f"pooled {iv.method} over {len(ms)} experiment(s)", metrics=ms,
            how_measured=HOW.get(code, types_by_dim.get(code, ""))))
    measured = sum(d.measured for d in dims)
    notes = [f"{measured} of 8 dimensions measured; unmeasured dimensions are shown as such, not as zero.",
             "Pooling adds runs from different experiments. Check each experiment's design before treating them as one sample."]
    return FingerprintOut(model_id=model.id, model_slug=model.slug, display_name=model.display_name, version=version_label,
                          includes_demo_data=model.is_mock, dimensions=dims, notes=notes)
