from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvalResult:
    score: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class Evaluator(ABC):
    name: str
    version: str = "1"
    kind: str = "deterministic"  # LLM judges (Phase 3+) must set "llm_judge" and be labelled in the UI

    @abstractmethod
    def evaluate(self, response: str, expected: str | None) -> EvalResult: ...
