from app.evaluators.base import Evaluator
from app.evaluators.exact import ExactMatch
from app.evaluators.numeric import NumericMatch

_EVALUATORS: dict[str, Evaluator] = {e.name: e for e in (ExactMatch(), NumericMatch())}


def get_evaluator(name: str) -> Evaluator:
    try:
        return _EVALUATORS[name]
    except KeyError:
        raise KeyError(f"unknown evaluator {name!r}; available: {sorted(_EVALUATORS)}") from None


def list_evaluators() -> list[str]:
    return sorted(_EVALUATORS)
