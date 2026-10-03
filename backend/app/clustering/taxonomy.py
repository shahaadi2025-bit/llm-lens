"""Deterministic error taxonomy for incorrect answers. Rule-based so it is reproducible and auditable."""
import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")

ERROR_TYPES = {
    "empty_response": "Empty response",
    "no_numeric_answer": "No numeric answer (format / instruction failure)",
    "numeric_near_miss": "Numeric near miss (within 1%)",
    "numeric_far_miss": "Numeric far miss (off by more than 1%)",
    "wrong_text": "Wrong text answer",
}


def classify_failure(response: str, expected: str | None) -> str:
    if not response.strip():
        return "empty_response"
    if expected is None:
        return "wrong_text"
    try:
        exp = Decimal(expected.replace(",", ""))
    except InvalidOperation:
        return "wrong_text"
    found = _NUMBER.findall(response)
    if not found:
        return "no_numeric_answer"
    got = Decimal(found[-1].replace(",", ""))
    if exp == 0:
        return "numeric_far_miss"
    return "numeric_near_miss" if abs(got - exp) / abs(exp) <= Decimal("0.01") else "numeric_far_miss"
