from app.experiments.types.arithmetic import ArithmeticRepresentation
from app.experiments.types.base import ExperimentType

_TYPES: dict[str, ExperimentType] = {t.task_type: t for t in (ArithmeticRepresentation(),)}


def get_experiment_type(task_type: str) -> ExperimentType:
    try:
        return _TYPES[task_type]
    except KeyError:
        raise KeyError(f"unknown task_type {task_type!r}; available: {sorted(_TYPES)}") from None


def list_experiment_types() -> list[ExperimentType]:
    return list(_TYPES.values())
