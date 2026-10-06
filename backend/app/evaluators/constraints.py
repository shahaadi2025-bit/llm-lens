"""Deterministic checker for verifiable instructions. The expected value is a JSON list of constraint specs; the score is the
fraction satisfied and an answer passes only if every constraint is satisfied. No model judges anything here."""
import json
import re

from app.evaluators.base import EvalResult, Evaluator

_WORD = re.compile(r"[A-Za-z0-9'’-]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

DESCRIPTIONS = {
    "max_words": "Use at most {n} words.",
    "include": "Include the word '{word}'.",
    "exclude": "Do not use the word '{word}'.",
    "lowercase": "Write entirely in lowercase.",
    "starts_with": "Begin your answer with '{text}'.",
    "ends_with": "End your answer with '{text}'.",
    "sentences": "Write exactly {n} sentences.",
}


def describe(spec: dict) -> str:
    return DESCRIPTIONS[spec["type"]].format(**{k: v for k, v in spec.items() if k != "type"})


def _contains_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def check_one(text: str, spec: dict) -> bool:
    t = text.strip()
    kind = spec["type"]
    if kind == "max_words":
        return len(_WORD.findall(t)) <= spec["n"]
    if kind == "include":
        return _contains_word(t, spec["word"])
    if kind == "exclude":
        return not _contains_word(t, spec["word"])
    if kind == "lowercase":
        return bool(t) and t == t.lower()
    if kind == "starts_with":
        return t.startswith(spec["text"])
    if kind == "ends_with":
        return t.endswith(spec["text"])
    if kind == "sentences":
        return len([s for s in _SENTENCE_SPLIT.split(t) if s.strip()]) == spec["n"]
    raise ValueError(f"unknown constraint type {kind!r}")


class ConstraintCheck(Evaluator):
    name = "constraint_check"
    version = "1"

    def evaluate(self, response: str, expected: str | None) -> EvalResult:
        if not expected:
            return EvalResult(0.0, False, {"reason": "no_expected_constraints"})
        try:
            specs = json.loads(expected)["constraints"]
            results = [{"constraint": describe(s), "satisfied": check_one(response, s)} for s in specs]
        except (ValueError, KeyError, TypeError):
            return EvalResult(0.0, False, {"reason": "unparseable_constraints"})
        if not response.strip():
            return EvalResult(0.0, False, {"reason": "empty_response", "results": results})
        ok = sum(1 for r in results if r["satisfied"])
        return EvalResult(ok / len(results), ok == len(results), {"satisfied": ok, "total": len(results), "results": results})
