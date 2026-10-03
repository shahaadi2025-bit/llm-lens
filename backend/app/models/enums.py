"""String enums. Stored as plain VARCHAR (not native DB enums) to keep migrations portable."""
from enum import StrEnum


class ExperimentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluatorKind(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"  # always labeled "LLM-based evaluation" in the UI
    HUMAN = "human"


class EvidenceLevel(StrEnum):
    """Epistemic status of a statement. Reports must never skip levels."""
    OBSERVATION = "observation"
    CORRELATION = "correlation"
    HYPOTHESIS = "hypothesis"
    SUPPORTED_CONCLUSION = "supported_conclusion"


class AnomalyStatus(StrEnum):
    POTENTIAL_ANOMALY = "potential_anomaly"  # never "model failure" automatically
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    DISMISSED = "dismissed"


class FingerprintDimension(StrEnum):
    REASONING = "R"
    MATHEMATICS = "M"
    FACTUALITY = "F"
    CONTEXT = "C"
    INSTRUCTION = "I"
    HALLUCINATION = "H"
    TOOL_USE = "T"
    STABILITY = "S"
