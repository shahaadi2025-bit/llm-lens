import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.experiment import ExperimentOut

NOTE_KINDS = ("observation", "note", "hypothesis")


class ReportCreate(BaseModel):
    experiment_id: uuid.UUID | None = None
    investigation_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _exactly_one(self) -> "ReportCreate":
        if (self.experiment_id is None) == (self.investigation_id is None):
            raise ValueError("provide exactly one of experiment_id or investigation_id")
        return self


class ReportSummary(BaseModel):
    id: uuid.UUID
    title: str
    experiment_id: uuid.UUID | None
    investigation_id: uuid.UUID | None
    includes_demo_data: bool
    owned_by_me: bool
    created_at: datetime


class ReportOut(ReportSummary):
    content: str


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    research_question: str = Field(default="", max_length=3000)
    hypothesis: str = Field(default="", max_length=3000)


class InvestigationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    research_question: str | None = Field(default=None, max_length=3000)
    hypothesis: str | None = Field(default=None, max_length=3000)
    conclusion: str | None = Field(default=None, max_length=4000)
    limitations: str | None = Field(default=None, max_length=4000)


class NoteCreate(BaseModel):
    kind: str
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in NOTE_KINDS:
            raise ValueError(f"kind must be one of {NOTE_KINDS}")
        return v


class NoteOut(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    created_at: datetime


class LinkExperiment(BaseModel):
    experiment_id: uuid.UUID


class InvestigationSummary(BaseModel):
    id: uuid.UUID
    title: str
    research_question: str
    n_experiments: int
    n_notes: int
    has_conclusion: bool
    updated_at: datetime


class InvestigationDetail(BaseModel):
    id: uuid.UUID
    title: str
    research_question: str
    hypothesis: str
    conclusion: str
    limitations: str
    experiments: list[ExperimentOut]
    hidden_experiments: int
    notes: list[NoteOut]
    created_at: datetime
    updated_at: datetime
