from app.experiments.types.arithmetic import ArithmeticRepresentation
from app.experiments.types.base import ExperimentType
from app.experiments.types.context_retrieval import ContextLength, ContextPosition
from app.experiments.types.instruction_following import InstructionOrdering
from app.experiments.types.prompt_sensitivity import PromptSensitivity

_TYPES: dict[str, ExperimentType] = {t.task_type: t for t in (
    ArithmeticRepresentation(), PromptSensitivity(), InstructionOrdering(), ContextPosition(), ContextLength(),
)}


def get_experiment_type(task_type: str) -> ExperimentType:
    try:
        return _TYPES[task_type]
    except KeyError:
        raise KeyError(f"unknown task_type {task_type!r}; available: {sorted(_TYPES)}") from None


def list_experiment_types() -> list[ExperimentType]:
    return list(_TYPES.values())
