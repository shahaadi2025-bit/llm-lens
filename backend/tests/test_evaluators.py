import pytest

from app.evaluators.exact import ExactMatch
from app.evaluators.numeric import NumericMatch
from app.evaluators.registry import get_evaluator


@pytest.mark.parametrize("text,ok", [
    ("The answer is 3108.", True), ("3,108", True), ("3108", True), ("It is 3108 (not 3180).", False),
    ("The answer is 3109.", False), ("I don't know", False), ("", False), ("-5", False),
])
def test_numeric_match(text, ok):
    r = NumericMatch().evaluate(text, "3108")
    assert r.passed is ok
    assert r.score == (1.0 if ok else 0.0)
    assert r.details["rule"] == "last_number_in_response"


def test_numeric_match_reports_reason_for_empty_and_missing_expected():
    assert NumericMatch().evaluate("", "5").details["reason"] == "empty_response"
    assert NumericMatch().evaluate("abc", "5").details["reason"] == "no_number_found"
    assert NumericMatch().evaluate("5", None).details["reason"] == "no_expected_answer"


def test_numeric_negative_and_decimal():
    assert NumericMatch().evaluate("x = -2.50", "-2.5").passed


def test_exact_match_normalizes_case_and_whitespace():
    assert ExactMatch().evaluate("  Paris \n", "paris").passed
    assert not ExactMatch().evaluate("Lyon", "Paris").passed


def test_registry_unknown_evaluator():
    with pytest.raises(KeyError):
        get_evaluator("nope")
