import uuid

from pydantic import BaseModel

from app.schemas.failures import FailureOut


class ClusterOut(BaseModel):
    id: uuid.UUID
    label: str
    size: int
    method: str
    embedding_model: str | None
    error_types: dict[str, int]
    forms: dict[str, int]
    includes_demo_data: bool
    note: str


class ClusterDetail(ClusterOut):
    members: list[FailureOut]
