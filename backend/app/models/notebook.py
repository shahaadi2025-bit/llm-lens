import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedMixin, IdMixin, utcnow


class Investigation(Base, IdMixin, CreatedMixin):
    """A research notebook entry: question, hypothesis, linked experiments, notes, conclusion and its limitations.
    Private to its owner."""
    __tablename__ = "investigations"

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    research_question: Mapped[str] = mapped_column(Text, default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InvestigationExperiment(Base):
    __tablename__ = "investigation_experiments"

    investigation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("investigations.id"), primary_key=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("experiments.id"), primary_key=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InvestigationNote(Base, IdMixin, CreatedMixin):
    __tablename__ = "investigation_notes"

    investigation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("investigations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # observation | note | hypothesis
    text: Mapped[str] = mapped_column(Text)
