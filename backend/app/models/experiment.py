import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, IdMixin
from app.models.enums import ExperimentStatus, RunStatus


class ExperimentConfig(Base, IdMixin, CreatedMixin):
    """A saved, reusable experiment configuration."""
    __tablename__ = "experiment_configs"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(60))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)


class Experiment(Base, IdMixin, CreatedMixin):
    __tablename__ = "experiments"
    __table_args__ = (
        Index("ix_experiments_status_created", "status", "created_at"),
        Index("ix_experiments_type_model", "task_type", "model_version_id"),
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("model_versions.id"), index=True)
    config_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("experiment_configs.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(200))
    research_question: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ExperimentStatus.PENDING.value)

    # Sampling parameters
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    max_tokens: Mapped[int] = mapped_column(Integer, default=256)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repetitions: Mapped[int] = mapped_column(Integer, default=1)

    # Evaluation + data
    evaluator: Mapped[str] = mapped_column(String(80))
    dataset_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dataset_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    spec_hash: Mapped[str] = mapped_column(String(64), index=True, default="", server_default="")  # duplicate detection

    # Reproducibility record (software versions, hardware, library versions)
    software_version: Mapped[str] = mapped_column(String(40))
    environment: Mapped[dict] = mapped_column(JSON, default=dict)

    # Visibility / provenance
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, default=False)  # True = NOT real LLM evidence

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    runs: Mapped[list["ExperimentRun"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")


class ExperimentLineage(Base, IdMixin, CreatedMixin):
    """Directed edge in the investigation graph: parent -> follow-up child."""
    __tablename__ = "experiment_lineage"
    __table_args__ = (UniqueConstraint("parent_experiment_id", "child_experiment_id"),)

    parent_experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiments.id"), index=True)
    child_experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiments.id"), index=True)
    trigger_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), nullable=True)
    relation: Mapped[str] = mapped_column(String(40), default="follow_up")  # follow_up | clone | rerun
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExperimentRun(Base, IdMixin):
    """One model call: a single prompt variant x repetition."""
    __tablename__ = "experiment_runs"
    __table_args__ = (UniqueConstraint("experiment_id", "run_index"),)

    experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiments.id"), index=True)
    run_index: Mapped[int] = mapped_column(Integer)
    variant_label: Mapped[str] = mapped_column(String(120), default="base")
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.PENDING.value, index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiment: Mapped[Experiment] = relationship(back_populates="runs")


class Prompt(Base, IdMixin, CreatedMixin):
    __tablename__ = "prompts"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiment_runs.id"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    system_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    variant_kind: Mapped[str] = mapped_column(String(60), default="base")
    variant_params: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # duplicate detection
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
