import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    research_question: str | None = Field(default=None, max_length=2000)  # defaults to the type's documented question
    hypothesis: str | None = Field(default=None, max_length=2000)
    task_type: str
    model_slug: str | None = None  # defaults to the configured model
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=64, ge=1, le=2048)
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    repetitions: int = Field(default=1, ge=1, le=20)
    evaluator: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_public: bool = False


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    evaluator_name: str
    evaluator_version: str
    score: float
    passed: bool | None
    details: dict[str, Any]


class RunOut(BaseModel):
    id: uuid.UUID
    run_index: int
    variant_label: str
    variant_params: dict[str, Any]
    status: str
    attempt: int
    seed: int
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    tokens_estimated: bool
    error: str | None
    prompt: str
    expected_answer: str | None
    response: str | None
    evaluation: EvaluationOut | None


class RunCounts(BaseModel):
    total: int = 0
    pending: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    passed: int = 0  # succeeded runs the evaluator marked correct (raw count; statistics arrive in Phase 3)


class ExperimentOut(BaseModel):
    id: uuid.UUID
    name: str
    research_question: str
    hypothesis: str | None
    task_type: str
    status: str
    model_slug: str
    model_version: str
    is_demo_data: bool
    evaluator: str
    temperature: float
    max_tokens: int
    seed: int
    repetitions: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    counts: RunCounts


class ExperimentDetail(ExperimentOut):
    config: dict[str, Any]
    environment: dict[str, Any]
    software_version: str
    runs: list[RunOut]
    notice: str | None = None


class ExperimentTypeOut(BaseModel):
    task_type: str
    title: str
    research_question: str
    description: str
    default_evaluator: str
    default_config: dict[str, Any]


class ModelOut(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    provider: str
    context_length: int
    capabilities: dict[str, Any]
    is_mock: bool
    versions: list[str]
    experiment_count: int
    configured: bool  # True = the model this server is currently set up to run
