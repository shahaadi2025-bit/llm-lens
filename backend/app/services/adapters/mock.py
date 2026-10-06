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
_VAULT_FACT = re.compile(r"access code for vault (\w+) is (\d+)")
_VAULT_Q = re.compile(r"What is the access code for vault (\w+)\?")
_CONSTRAINT_LINE = re.compile(r"^- (.+)$", re.MULTILINE)
_FILLER = ["it", "stands", "near", "the", "old", "sea", "and", "waits", "for", "calm", "light", "today"]
ERROR_PERCENT = 15  # v1; v2 uses a higher rate so version comparison has something to detect

# slug -> (version label, display name, injected error percent)
MOCK_MODELS: dict[str, tuple[str, str, int]] = {
    "mock-deterministic-v1": ("mock-1", "Mock v1 (deterministic, not a real LLM)", 15),
    "mock-deterministic-v2": ("mock-2", "Mock v2 (deterministic, higher injected error rate)", 35),
}


def _parse_constraints(prompt: str) -> list[tuple[str, str]]:
    """Read the instruction lines this project's own templates generate (this is a mock: it does not understand English)."""
    out: list[tuple[str, str]] = []
    for line in _CONSTRAINT_LINE.findall(prompt):
        if m := re.fullmatch(r"Use at most (\d+) words\.", line):
            out.append(("max_words", m.group(1)))
        elif m := re.fullmatch(r"Include the word '(.+)'\.", line):
            out.append(("include", m.group(1)))
        elif m := re.fullmatch(r"Do not use the word '(.+)'\.", line):
            out.append(("exclude", m.group(1)))
        elif line == "Write entirely in lowercase.":
            out.append(("lowercase", ""))
        elif m := re.fullmatch(r"Begin your answer with '(.+)'\.", line):
            out.append(("starts_with", m.group(1)))
        elif m := re.fullmatch(r"End your answer with '(.+)'\.", line):
            out.append(("ends_with", m.group(1)))
        elif m := re.fullmatch(r"Write exactly (\d+) sentences\.", line):
            out.append(("sentences", m.group(1)))
    return out


def _compliant_text(cons: list[tuple[str, str]]) -> str:
    d = dict(cons)
    n = int(d.get("sentences", 2))
    sents = [" ".join(_FILLER[(i * 4 + j) % len(_FILLER)] for j in range(4)) + "." for i in range(n)]
    if "include" in d:
        sents[0] = sents[0][:-1] + f" {d['include']}."
    if "starts_with" in d:
        sents[0] = f"{d['starts_with']} {sents[0]}"
    if "ends_with" in d:
        sents[-1] = sents[-1][:-1] + f" {d['ends_with']}"
    return " ".join(sents)


def _violate(text: str, cons: list[tuple[str, str]], pick: int) -> str:
    """Break exactly one constraint, chosen from the constraint types in a canonical order."""
    kinds = sorted(k for k, _ in cons)
    kind = kinds[pick % len(kinds)]
    d = dict(cons)
    if kind == "max_words":
        return text + " " + " ".join(_FILLER * 6)
    if kind == "include":
        return text.replace(d["include"], "plain")
    if kind == "exclude":
        return text + f" {d['exclude']}."
    if kind == "lowercase":
        return text[:1].upper() + text[1:]
    if kind == "starts_with":
        return text.replace(d["starts_with"] + " ", "", 1)
    if kind == "ends_with":
        return text.rstrip(".") + " thanks."
    return text + " Extra sentence here."


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
        cons = _parse_constraints(request.prompt)
        q = _VAULT_Q.search(request.prompt)
        matches = [m for rx in (_MULT, _GROUPS, _PRODUCT) for m in rx.finditer(request.prompt)]
        match = max(matches, key=lambda m: m.end()) if matches else None  # the real question comes last
        if cons:  # instruction following: comply, except for uniform pseudo-random slips (not tied to instruction order)
            text = _compliant_text(cons)
            if digest % 100 < self._error:
                text = _violate(text, cons, (digest // 100) % 7)
        elif q:  # retrieval: read the fact for the named vault, with the same uniform error rate (no position effect injected)
            facts = dict(_VAULT_FACT.findall(request.prompt))
            code = facts.get(q.group(1))
            if code is None:
                text = "I could not find that vault."
            else:
                if digest % 100 < self._error:
                    code = str(int(code) + (digest // 100) % 9 + 1)
                text = f"The access code is {code}."
        elif match:
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
