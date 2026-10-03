"""Deterministic prompt mutations: change ONE surface property of a prompt while keeping its meaning.

The paraphrase here is a rule-based template rewrite, not an LLM paraphrase, so it is reproducible and cannot
drift. Each mutation returns its kind and parameters so results can be grouped and traced back to the change.
"""
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Mutation:
    kind: str
    text: str
    params: dict[str, Any] = field(default_factory=dict)


DISTRACTORS = [
    "The weather report mentioned light rain in the afternoon.",
    "A library on the corner opens at nine in the morning.",
    "Last week's meeting notes were filed in the shared folder.",
    "The train to the coast leaves from the second platform.",
]
FEW_SHOT = "Example: What is 6 × 7? Reply with only the number.\nAnswer: 42\n\n"
_MUL_Q = re.compile(r"What is (\d+) × (\d+)\?")


def _base(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"{q} {i}", {}


def _instruction_first(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"{i} {q}", {"change": "sentence_order"}


def _upper(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"{q} {i}".upper(), {"change": "capitalization"}


def _lower(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"{q} {i}".lower(), {"change": "capitalization"}


def _markdown(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"**Question:** {q}\n\n_{i}_", {"change": "formatting"}


def _whitespace(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"  {q}\n\n\n{i}  ", {"change": "formatting"}


def _irrelevant(q: str, i: str, rng: random.Random) -> tuple[str, dict[str, Any]]:
    d = rng.choice(DISTRACTORS)
    return f"{d} {q} {i}", {"change": "irrelevant_context", "distractor": d}


def _few_shot(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    return f"{FEW_SHOT}{q} {i}", {"change": "examples"}


def _paraphrase(q: str, i: str, _rng: random.Random) -> tuple[str, dict[str, Any]]:
    m = _MUL_Q.fullmatch(q)
    rewritten = f"Compute the product of {m.group(1)} and {m.group(2)}." if m else q
    return f"{rewritten} {i}", {"change": "paraphrase", "method": "rule-based template"}


MUTATORS: dict[str, Callable[[str, str, random.Random], tuple[str, dict[str, Any]]]] = {
    "base": _base, "instruction_first": _instruction_first, "uppercase": _upper, "lowercase": _lower,
    "markdown_format": _markdown, "extra_whitespace": _whitespace, "irrelevant_context": _irrelevant,
    "few_shot_example": _few_shot, "paraphrase": _paraphrase,
}


def generate_mutations(question: str, instruction: str, kinds: list[str] | None = None, seed: int = 0) -> list[Mutation]:
    """The 'base' form is always included first, as the reference every mutation is compared against."""
    chosen = ["base"] + [k for k in (kinds or list(MUTATORS)) if k != "base"]
    unknown = [k for k in chosen if k not in MUTATORS]
    if unknown:
        raise ValueError(f"unknown mutation kinds: {unknown}; available: {sorted(MUTATORS)}")
    out = []
    for kind in chosen:
        rng = random.Random(f"{seed}|{question}|{kind}")  # independent, reproducible stream per (question, kind)
        text, params = MUTATORS[kind](question, instruction, rng)
        out.append(Mutation(kind, text, params))
    return out
