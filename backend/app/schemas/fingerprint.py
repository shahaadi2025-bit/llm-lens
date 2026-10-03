import uuid

from pydantic import BaseModel


class DimensionMetric(BaseModel):
    metric_id: uuid.UUID
    experiment_id: uuid.UUID
    experiment_name: str
    version: str
    value: float
    ci_low: float | None
    ci_high: float | None
    n: int


class DimensionOut(BaseModel):
    code: str
    name: str
    measured: bool
    value: float | None
    ci_low: float | None
    ci_high: float | None
    n: int
    n_experiments: int
    method: str | None
    metrics: list[DimensionMetric]
    how_measured: str


class FingerprintOut(BaseModel):
    model_id: uuid.UUID
    model_slug: str
    display_name: str
    version: str | None
    includes_demo_data: bool
    dimensions: list[DimensionOut]
    notes: list[str]


class DiffOut(BaseModel):
    metric: str
    dimension: str | None
    a_value: float
    a_n: int
    b_value: float
    b_n: int
    difference: float  # b - a
    diff_ci_low: float
    diff_ci_high: float
    cohens_h: float
    mcnemar_p: float | None
    paired_only_a: int | None
    paired_only_b: int | None
    statement: str


class ExperimentRef(BaseModel):
    id: uuid.UUID
    name: str


class MatchedDesign(BaseModel):
    task_type: str
    a: ExperimentRef
    b: ExperimentRef


class CompareOut(BaseModel):
    a_label: str
    b_label: str
    includes_demo_data: bool
    comparable: bool
    matched: list[MatchedDesign]
    unmatched_a: list[ExperimentRef]
    unmatched_b: list[ExperimentRef]
    differences: list[DiffOut]
    latency_ms: dict[str, float | None]
    notes: list[str]
