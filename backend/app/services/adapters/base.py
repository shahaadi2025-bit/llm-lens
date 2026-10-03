"""ModelAdapter: the only interface the experiment engine knows about."""
import math
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


class AdapterError(Exception):
    """Any provider-side failure (network, bad response, missing dependency)."""


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    system: str | None = None
    temperature: float = 0.0
    max_tokens: int = 256
    seed: int = 0


@dataclass
class GenerationResult:
    text: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None  # None = provider did not report; engine falls back to an estimate
    completion_tokens: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    slug: str
    display_name: str
    provider: str
    context_length: int
    version_label: str = "default"
    revision: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    is_mock: bool = False


class ModelAdapter(ABC):
    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo: ...

    async def stream(self, request: GenerationRequest) -> AsyncIterator[str]:
        """Default: yield the full completion once. Providers with native streaming override this."""
        yield (await self.generate(request)).text

    def estimate_tokens(self, text: str) -> int:
        """Rough heuristic (~4 characters per token). Not tokenizer-exact; results using it are flagged as estimates."""
        return math.ceil(len(text) / 4) if text else 0
