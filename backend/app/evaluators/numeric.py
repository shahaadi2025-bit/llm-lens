import re
from decimal import Decimal, InvalidOperation

from app.evaluators.base import EvalResult, Evaluator

_NUMBER = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


class NumericMatch(Evaluator):
    """Extracts the LAST number in the response and compares it exactly to the expected value.

    Known limitation (recorded in every result's details): a response that states the right number and then
    appends an unrelated number is scored wrong. Extraction rule is stored so results stay interpretable.
    """
    name = "numeric_match"
    version = "1"
    RULE = "last_number_in_response"

    def evaluate(self, response: str, expected: str | None) -> EvalResult:
        details: dict[str, object] = {"rule": self.RULE, "expected": expected}
        if expected is None:
            return EvalResult(0.0, False, {**details, "reason": "no_expected_answer"})
        found = _NUMBER.findall(response)
        details["numbers_found"] = len(found)
        if not found:
            reason = "empty_response" if not response.strip() else "no_number_found"
            return EvalResult(0.0, False, {**details, "reason": reason})
        extracted = found[-1].replace(",", "")
        details["extracted"] = extracted
        try:
            ok = Decimal(extracted) == Decimal(expected.replace(",", ""))
        except InvalidOperation:
            return EvalResult(0.0, False, {**details, "reason": "unparseable_expected"})
        return EvalResult(1.0 if ok else 0.0, ok, details)
