import uuid
from typing import Any

from pydantic import BaseModel


class FailureOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    experiment_id: uuid.UUID
    experiment_name: str
    label: str
    detector: str
    status: str  # potential_anomaly | reproduced | not_reproduced | dismissed
    details: dict[str, Any]
    prompt: str
    response: str | None
    expected_answer: str | None
    is_demo_data: bool
    can_follow_up: bool


class FollowUpRequest(BaseModel):
    failure_id: uuid.UUID


class ExplainStep(BaseModel):
    text: str
    evidence_level: str | None = None


class FollowUpSummary(BaseModel):
    experiment_id: uuid.UUID
    name: str
    status: str
    summary: str | None


class EvidenceOut(BaseModel):
    level: str
    strength: str  # none | weak | moderate | strong
    status: str
    summary: str


class ExplainOut(BaseModel):
    failure: FailureOut
    observed: str
    controlled_variables: list[str]
    changed_variable: str
    follow_ups: list[FollowUpSummary]
    evidence: EvidenceOut
    possible_explanations: list[ExplainStep]
    alternative_explanations: list[ExplainStep]
    limitations: list[str]
    demo_notice: str | None


class LineageNode(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    is_current: bool
    is_demo_data: bool
    anomalies: int


class LineageEdge(BaseModel):
    parent: uuid.UUID
    child: uuid.UUID
    relation: str
    trigger_run_id: uuid.UUID | None
    note: str | None


class LineageOut(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
