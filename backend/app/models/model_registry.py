import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedMixin, IdMixin


class LLMModel(Base, IdMixin, CreatedMixin):
    """A model family as the platform knows it (e.g. a Qwen instruct model)."""
    __tablename__ = "models"

    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(50), index=True)
    context_length: Mapped[int] = mapped_column(Integer)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)

    versions: Mapped[list["ModelVersion"]] = relationship(back_populates="model")


class ModelVersion(Base, IdMixin, CreatedMixin):
    """A specific, pinnable version (e.g. HF revision hash) so experiments stay reproducible."""
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version_label"),)

    model_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("models.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(120))
    revision: Mapped[str | None] = mapped_column(String(120), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)

    model: Mapped[LLMModel] = relationship(back_populates="versions")
