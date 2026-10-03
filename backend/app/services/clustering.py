"""Cluster incorrect answers so similar failures can be inspected together. Clusters describe similarity of the
failing outputs; they are not causes."""
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering.embeddings import get_embedder, normalise_for_embedding
from app.clustering.kmeans import cluster
from app.clustering.taxonomy import ERROR_TYPES, classify_failure
from app.core.config import Settings
from app.experiments.registry import get_experiment_type
from app.models import Evaluation, Experiment, ExperimentRun, FailureCluster, FailureMode, Prompt, Response
from app.models.enums import AnomalyStatus, RunStatus

EVALUATOR_LABEL = "incorrect_answer"
MAX_RUNS = 2000


@dataclass
class _Item:
    run_id: object
    experiment_id: object
    task_type: str
    group: str | None
    error_type: str
    text: str


def describe(items: list[_Item]) -> str:
    """Label from facts about the members: dominant error type and, if one dominates, dominant prompt form."""
    types = Counter(i.error_type for i in items)
    et, _ = types.most_common(1)[0]
    groups = Counter(i.group for i in items if i.group)
    base = ERROR_TYPES[et]
    if groups:
        g, c = groups.most_common(1)[0]
        if c / len(items) >= 0.5 and len(groups) > 1:
            return f"{base}: mostly form '{g}' ({c / len(items):.0%})"
    return f"{base}: mixed forms" if len(groups) > 1 else base


async def recompute_clusters(session: AsyncSession, settings: Settings, seed: int = 0) -> list[FailureCluster]:
    rows = (await session.execute(
        select(ExperimentRun.id, Experiment.id, Experiment.task_type, Prompt.variant_params, Prompt.text,
               Prompt.expected_answer, Response.text)
        .join(Experiment, Experiment.id == ExperimentRun.experiment_id)
        .join(Prompt, Prompt.run_id == ExperimentRun.id).join(Response, Response.run_id == ExperimentRun.id)
        .join(Evaluation, Evaluation.run_id == ExperimentRun.id)
        .where(ExperimentRun.status == RunStatus.SUCCEEDED.value, Evaluation.passed.is_(False))
        .order_by(ExperimentRun.finished_at.desc()).limit(MAX_RUNS))).all()

    items: list[_Item] = []
    for run_id, exp_id, task_type, params, prompt, expected, response in rows:
        try:
            group = get_experiment_type(task_type).group_of(params)
        except KeyError:
            group = None
        et = classify_failure(response, expected)
        items.append(_Item(run_id, exp_id, task_type, group, et,
                           normalise_for_embedding(f"form={group} type={et} prompt={prompt} response={response}")))

    # Replace previous clustering (members first, then clusters). Anomaly flags from detectors are untouched.
    await session.execute(delete(FailureMode).where(FailureMode.label == EVALUATOR_LABEL))
    await session.execute(delete(FailureCluster))
    if not items:
        await session.commit()
        return []

    embedder = get_embedder(settings.embeddings_backend)
    result = cluster(embedder.embed([i.text for i in items]), len(items))
    clusters: list[FailureCluster] = []
    for c in range(result.k):
        members = [it for it, lab in zip(items, result.labels, strict=True) if lab == c]
        fc = FailureCluster(label=describe(members), method=f"kmeans(k={result.k}, silhouette={result.silhouette})"
                            if result.silhouette is not None else "single-cluster (too few failures or no separable structure)",
                            size=len(members), centroid=None, embedding_model=embedder.name)
        session.add(fc)
        await session.flush()
        session.add_all([FailureMode(
            run_id=m.run_id, cluster_id=fc.id, label=EVALUATOR_LABEL, detector="evaluator",
            status=AnomalyStatus.OBSERVED_INCORRECT.value,
            details={"error_type": m.error_type, "group": m.group, "task_type": m.task_type,
                     "experiment_id": str(m.experiment_id)}) for m in members])
        clusters.append(fc)
    await session.commit()
    return clusters
