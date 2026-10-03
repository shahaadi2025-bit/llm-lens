import uuid

from sqlalchemy import select

from app.models import (
    Evaluation,
    Experiment,
    ExperimentRun,
    LLMModel,
    Metric,
    MetricEvidence,
    ModelVersion,
    Prompt,
    Response,
)
from app.models.base import Base

REQUIRED_TABLES = {
    "users", "models", "model_versions", "experiments", "experiment_runs", "prompts", "responses",
    "evaluations", "metrics", "failure_modes", "failure_clusters", "experiment_configs", "reports",
}


def test_required_tables_exist_in_metadata():
    assert REQUIRED_TABLES <= set(Base.metadata.tables)


async def test_evidence_chain_roundtrip(session):
    """metric -> run -> prompt -> response -> evaluation must all be linkable."""
    model = LLMModel(slug="mock", display_name="Mock", provider="mock", context_length=4096, is_mock=True)
    session.add(model)
    await session.flush()
    mv = ModelVersion(model_id=model.id, version_label="v1")
    session.add(mv)
    await session.flush()
    exp = Experiment(
        model_version_id=mv.id, name="t", research_question="q?", task_type="math", evaluator="exact",
        software_version="0.1.0", is_demo_data=True,
    )
    session.add(exp)
    await session.flush()
    run = ExperimentRun(experiment_id=exp.id, run_index=0)
    session.add(run)
    await session.flush()
    session.add_all([
        Prompt(run_id=run.id, text="2+2?", content_hash="h"),
        Response(run_id=run.id, text="4"),
        Evaluation(run_id=run.id, evaluator_name="exact", evaluator_version="1", score=1.0, passed=True),
    ])
    metric = Metric(experiment_id=exp.id, model_version_id=mv.id, name="accuracy", value=1.0, n=1, method="wilson")
    session.add(metric)
    await session.flush()
    session.add(MetricEvidence(metric_id=metric.id, run_id=run.id))
    await session.commit()

    rows = (await session.execute(
        select(Response.text, Evaluation.passed)
        .join(Evaluation, Evaluation.run_id == Response.run_id)
        .join(MetricEvidence, MetricEvidence.run_id == Response.run_id)
        .where(MetricEvidence.metric_id == metric.id)
    )).all()
    assert rows == [("4", True)]
    assert isinstance(exp.id, uuid.UUID)
