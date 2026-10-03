import re

from app.evaluators.base import EvalResult, Evaluator


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


class ExactMatch(Evaluator):
    """Whitespace- and case-insensitive equality. Deterministic."""
    name = "exact_match"

    def evaluate(self, response: str, expected: str | None) -> EvalResult:
        if expected is None:
            return EvalResult(0.0, False, {"reason": "no_expected_answer"})
        ok = _norm(response) == _norm(expected)
        return EvalResult(1.0 if ok else 0.0, ok, {"expected": expected, "normalized_response": _norm(response)})
