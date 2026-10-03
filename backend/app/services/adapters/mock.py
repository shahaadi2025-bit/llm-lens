"""Deterministic mock model. Its output is NOT real LLM behavior and must never be presented as evidence.

For multiplication prompts it computes the true product, then deterministically (hash of seed+prompt) returns a
wrong answer for ~15% of prompts so evaluators, statistics and anomaly detection have both outcomes to exercise.
"""
import hashlib
import re
import time

from app.services.adapters.base import GenerationRequest, GenerationResult, ModelAdapter, ModelInfo

_MULT = re.compile(r"(\d+)\s*(?:×|x|\*)\s*(\d+)")
_GROUPS = re.compile(r"(\d+)\s+groups\s+of\s+(\d+)", re.IGNORECASE)
_PRODUCT = re.compile(r"product\s+of\s+(\d+)\s+and\s+(\d+)", re.IGNORECASE)
ERROR_PERCENT = 15  # v1; v2 uses a higher rate so version comparison has something to detect

# slug -> (version label, display name, injected error percent)
MOCK_MODELS: dict[str, tuple[str, str, int]] = {
    "mock-deterministic-v1": ("mock-1", "Mock v1 (deterministic, not a real LLM)", 15),
    "mock-deterministic-v2": ("mock-2", "Mock v2 (deterministic, higher injected error rate)", 35),
}


class MockAdapter(ModelAdapter):
    def __init__(self, model_name: str = "mock-deterministic-v1", context_length: int = 4096) -> None:
        self._name = model_name
        self._ctx = context_length
        self._label, self._display, self._error = MOCK_MODELS.get(model_name, MOCK_MODELS["mock-deterministic-v1"])

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            slug=self._name, display_name=self._display, provider="mock",
            context_length=self._ctx, version_label=self._label, is_mock=True,
            capabilities={"math": True, "streaming": False},
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        start = time.perf_counter()
        digest = int(hashlib.sha256(f"{request.seed}|{request.prompt}".encode()).hexdigest()[:12], 16)
        matches = [m for rx in (_MULT, _GROUPS, _PRODUCT) for m in rx.finditer(request.prompt)]
        match = max(matches, key=lambda m: m.end()) if matches else None  # the real question comes last
        if match:
            value = int(match.group(1)) * int(match.group(2))
            if digest % 100 < self._error:
                delta = (digest // 100) % 9 + 1
                value += delta if (digest // 1000) % 2 else -delta
            text = f"The answer is {value}."
        else:
            text = "[MOCK] No real model was run for this prompt."
        elapsed = (time.perf_counter() - start) * 1000
        return GenerationResult(
            text=text, finish_reason="stop",
            prompt_tokens=self.estimate_tokens(request.prompt), completion_tokens=self.estimate_tokens(text),
            raw={"mock": True, "latency_ms_internal": round(elapsed, 3)},
        )
