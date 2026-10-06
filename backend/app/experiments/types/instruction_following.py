import json
import random
from typing import Any

from app.evaluators.constraints import describe
from app.experiments.types.base import ConfigError, ExperimentType, PromptItem

TOPICS = ["a lighthouse", "a bicycle", "a library", "a volcano", "a bridge", "a garden", "a train station", "a market",
          "a river", "a clock tower"]
INCLUDE_WORDS = ["bright", "quiet", "old", "steady", "narrow"]
EXCLUDE_WORDS = ["very", "really", "thing", "just"]
STARTS = ["indeed", "overall", "briefly"]
ENDS = ["that is all.", "end of note."]
ORDERINGS = ["listed", "reversed", "rotated", "shuffled"]
KINDS = ["max_words", "include", "exclude", "lowercase", "starts_with", "ends_with", "sentences"]


def _spec(kind: str, rng: random.Random) -> dict[str, Any]:
    if kind == "max_words":
        return {"type": kind, "n": rng.randint(25, 40)}
    if kind == "include":
        return {"type": kind, "word": rng.choice(INCLUDE_WORDS)}
    if kind == "exclude":
        return {"type": kind, "word": rng.choice(EXCLUDE_WORDS)}
    if kind == "lowercase":
        return {"type": kind}
    if kind == "starts_with":
        return {"type": kind, "text": rng.choice(STARTS)}
    if kind == "ends_with":
        return {"type": kind, "text": rng.choice(ENDS)}
    return {"type": kind, "n": rng.randint(2, 4)}


def _reorder(items: list, how: str, rng: random.Random) -> list:
    if how == "listed":
        return list(items)
    if how == "reversed":
        return list(reversed(items))
    if how == "rotated":
        return items[1:] + items[:1]
    out = list(items)
    for _ in range(10):  # a shuffle that is guaranteed to differ from the listed order when possible
        rng.shuffle(out)
        if out != items or len(items) < 2:
            break
    return out


class InstructionOrdering(ExperimentType):
    task_type = "instruction_ordering"
    title = "Instruction ordering sensitivity"
    research_question = (
        "Does the model satisfy the same set of verifiable instructions equally often when the instructions are listed in a "
        "different order?"
    )
    description = (
        "Each task has several machine-checkable constraints (word limit, required or forbidden word, lowercase, opening and "
        "closing text, sentence count). The same constraints are presented in different orders; a deterministic checker scores "
        "every answer, so no model judges another model."
    )
    default_evaluator = "constraint_check"
    fingerprint_dimension = "I"
    default_config: dict[str, Any] = {"n_tasks": 6, "n_constraints": 3, "orderings": ["reversed", "rotated", "shuffled"]}

    def group_of(self, variant_params: dict[str, Any]) -> str | None:
        return variant_params.get("ordering")

    def block_of(self, variant_params: dict[str, Any]) -> str | None:
        t = variant_params.get("task")
        return None if t is None else f"task{t}#{variant_params.get('repetition', 0)}"

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = {**self.default_config, **config}
        if not isinstance(cfg["n_tasks"], int) or not 1 <= cfg["n_tasks"] <= len(TOPICS):
            raise ConfigError(f"n_tasks must be an integer between 1 and {len(TOPICS)}")
        if not isinstance(cfg["n_constraints"], int) or not 2 <= cfg["n_constraints"] <= 5:
            raise ConfigError("n_constraints must be an integer between 2 and 5")
        o = cfg["orderings"]
        if not isinstance(o, list) or not o or any(x not in ORDERINGS or x == "listed" for x in o):
            raise ConfigError(f"orderings must be a non-empty list from {[x for x in ORDERINGS if x != 'listed']}")
        return cfg

    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        cfg = self.validate_config(config)
        items = []
        for t in range(cfg["n_tasks"]):
            rng = random.Random(f"{seed}|task|{t}")
            kinds = rng.sample(KINDS, cfg["n_constraints"])
            specs = [_spec(k, rng) for k in kinds]
            expected = json.dumps({"constraints": specs}, sort_keys=True)
            for how in ["listed", *cfg["orderings"]]:
                ordered = _reorder(specs, how, random.Random(f"{seed}|order|{t}|{how}"))
                lines = "\n".join(f"- {describe(s)}" for s in ordered)
                prompt = f"Write a short description of {TOPICS[t]}.\nFollow all of these instructions:\n{lines}"
                items.append(PromptItem(prompt=prompt, expected=expected, variant_kind="ordering", variant_label=f"task{t}:{how}",
                                        variant_params={"task": t, "ordering": how, "n_constraints": len(specs)}))
        return items
