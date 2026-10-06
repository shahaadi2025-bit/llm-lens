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
    fingerprint_dimension: str | None = None  # R M F C I H T S: which behavioral-fingerprint axis this feeds

    def group_of(self, variant_params: dict[str, Any]) -> str | None:
        """The form/condition a prompt belongs to (for comparing forms). None = no grouping."""
        return None

    def block_of(self, variant_params: dict[str, Any]) -> str | None:
        """The underlying problem instance, shared across forms (enables paired analysis)."""
        return None

    def validate_for_model(self, config: dict[str, Any], context_length: int) -> None:
        """Reject settings the chosen model cannot support (e.g. a context larger than its window). Default: no limits."""
        return None

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return a fully-populated, validated config (defaults filled in) or raise ConfigError."""

    @abstractmethod
    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        """Deterministic for a given (config, seed): this is what makes experiments reproducible."""
