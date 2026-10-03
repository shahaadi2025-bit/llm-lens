import random
from typing import Any

from app.experiments.mutations import MUTATORS, generate_mutations
from app.experiments.types.arithmetic import ANCHOR_PAIR
from app.experiments.types.base import ConfigError, ExperimentType, PromptItem

INSTRUCTION = "Reply with only the number."


class PromptSensitivity(ExperimentType):
    task_type = "prompt_sensitivity"
    title = "Prompt sensitivity"
    research_question = (
        "Does the correctness of a model's answer to the same multiplication change when the prompt's surface "
        "form is changed (paraphrase, capitalization, formatting, sentence order, irrelevant context, an example)?"
    )
    description = (
        "Each problem is asked in a reference form and several controlled mutations. Mutations are deterministic "
        "rewrites, so each difference traces to one named change. Base problems are multiplications so the answer "
        "can be checked exactly."
    )
    default_evaluator = "numeric_match"
    fingerprint_dimension = "S"
    default_config: dict[str, Any] = {"n_random_pairs": 2, "kinds": [k for k in MUTATORS if k != "base"]}

    def group_of(self, variant_params: dict[str, Any]) -> str | None:
        return variant_params.get("mutation")

    def block_of(self, variant_params: dict[str, Any]) -> str | None:
        pair = variant_params.get("pair")
        return f"{pair[0]}x{pair[1]}#{variant_params.get('repetition', 0)}" if pair else None

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = {**self.default_config, **config}
        kinds = cfg["kinds"]
        if not isinstance(kinds, list) or not kinds or any(k not in MUTATORS or k == "base" for k in kinds):
            raise ConfigError(f"kinds must be a non-empty list from {sorted(k for k in MUTATORS if k != 'base')}")
        n = cfg["n_random_pairs"]
        if not isinstance(n, int) or not 0 <= n <= 20:
            raise ConfigError("n_random_pairs must be an integer between 0 and 20")
        pairs = cfg.get("pairs")
        if pairs is not None and not (isinstance(pairs, list) and pairs and all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) and 2 <= x <= 9999 for x in p) for p in pairs)):
            raise ConfigError("pairs must be a non-empty list of [a, b] integers between 2 and 9999")
        return cfg

    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        cfg = self.validate_config(config)
        rng = random.Random(seed)
        pairs = [tuple(p) for p in cfg["pairs"]] if cfg.get("pairs") else [ANCHOR_PAIR]
        while not cfg.get("pairs") and len(pairs) < 1 + cfg["n_random_pairs"]:
            a, b = rng.randint(12, 99), rng.randint(12, 99)
            if a != b and (a, b) not in pairs and (b, a) not in pairs:
                pairs.append((a, b))
        items = []
        for a, b in pairs:
            for m in generate_mutations(f"What is {a} × {b}?", INSTRUCTION, cfg["kinds"], seed):
                items.append(PromptItem(
                    prompt=m.text, expected=str(a * b), variant_kind="mutation", variant_label=f"{a}x{b}:{m.kind}",
                    variant_params={"pair": [a, b], "mutation": m.kind, **m.params}))
        return items
