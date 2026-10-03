import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, IdMixin
from app.models.enums import AnomalyStatus


class FailureCluster(Base, IdMixin, CreatedMixin):
    __tablename__ = "failure_clusters"

    label: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer, default=0)
    centroid: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)


class FailureMode(Base, IdMixin, CreatedMixin):
    """A flagged run. Default status is POTENTIAL_ANOMALY, never "model failure"."""
    __tablename__ = "failure_modes"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), index=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("failure_clusters.id"), index=True, nullable=True)
    label: Mapped[str] = mapped_column(String(120), index=True)
    detector: Mapped[str] = mapped_column(String(60))  # iqr | zscore | isolation_forest | evaluator | embedding
    status: Mapped[str] = mapped_column(String(30), default=AnomalyStatus.POTENTIAL_ANOMALY.value)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Report(Base, IdMixin, CreatedMixin):
    __tablename__ = "reports"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("experiments.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    format: Mapped[str] = mapped_column(String(20), default="markdown")
    content: Mapped[str] = mapped_column(Text)
    includes_demo_data: Mapped[bool] = mapped_column(default=False)
