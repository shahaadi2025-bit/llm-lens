import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, IdMixin, utcnow
from app.models.enums import EvaluatorKind


class Response(Base, IdMixin, CreatedMixin):
    __tablename__ = "responses"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    finish_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_empty: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class Evaluation(Base, IdMixin, CreatedMixin):
    """Verdict on one response. LLM-judge fields are populated only for kind=llm_judge."""
    __tablename__ = "evaluations"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=EvaluatorKind.DETERMINISTIC.value)
    evaluator_name: Mapped[str] = mapped_column(String(80), index=True)
    evaluator_version: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    judge_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    judge_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)


class Metric(Base, IdMixin):
    """An aggregate number with its uncertainty. Always traceable via MetricEvidence."""
    __tablename__ = "metrics"

    experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiments.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("model_versions.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    dimension: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)  # R M F C I H T S
    value: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_level: Mapped[float] = mapped_column(Float, default=0.95)
    n: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(120))  # e.g. "wilson", "bootstrap-percentile-10000"
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricEvidence(Base):
    """Join table: metric -> the runs it was computed from (metric -> run -> prompt -> response -> evaluation)."""
    __tablename__ = "metric_evidence"

    metric_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("metrics.id"), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), primary_key=True, index=True)
