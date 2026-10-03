import uuid

from pydantic import BaseModel

from app.schemas.experiment import ExperimentOut, RunOut


class MetricOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    dimension: str | None
    value: float
    ci_low: float | None
    ci_high: float | None
    ci_level: float
    n: int
    method: str
    evidence_runs: int
    is_demo_data: bool


class MetricEvidenceOut(BaseModel):
    metric: MetricOut
    runs: list[RunOut]


class GroupStat(BaseModel):
    group: str
    accuracy: float
    ci_low: float
    ci_high: float
    n: int


class StatementOut(BaseModel):
    text: str
    evidence_level: str


class AnalysisOut(BaseModel):
    experiment_id: uuid.UUID
    is_demo_data: bool
    method: str
    groups: list[GroupStat]
    n_blocks: int
    cochran_q: float | None
    cochran_df: int | None
    cochran_p: float | None
    best: str | None
    worst: str | None
    spread: float | None
    cohens_h: float | None
    statements: list[StatementOut]
    limitations: list[str]


class DashboardOut(BaseModel):
    experiments_total: int
    experiments_completed: int
    models_tested: int
    potential_anomalies: int
    failure_clusters: int
    recent: list[ExperimentOut]
    includes_demo_data: bool
    notes: list[str]


