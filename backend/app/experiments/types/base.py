from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ConfigError(ValueError):
    """Invalid experiment-type configuration."""


@dataclass(frozen=True)
class PromptItem:
    prompt: str
    expected: str | None
    variant_kind: str
    variant_label: str
    variant_params: dict[str, Any] = field(default_factory=dict)
    system: str | None = None


class ExperimentType(ABC):
    task_type: str
    title: str
    research_question: str
    description: str
    default_evaluator: str
    default_config: dict[str, Any]

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a fully-populated, validated config (defaults filled in) or raise ConfigError."""

    @abstractmethod
    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        """Deterministic for a given (config, seed): this is what makes experiments reproducible."""
