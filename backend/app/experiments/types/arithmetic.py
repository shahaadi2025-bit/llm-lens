import random
from typing import Any

from app.experiments.types.base import ConfigError, ExperimentType, PromptItem

# Every representation asks for the same product a*b; only the surface form changes.
REPRESENTATIONS: dict[str, str] = {
    "a_x_b": "What is {a} × {b}? Reply with only the number.",
    "b_x_a": "What is {b} × {a}? Reply with only the number.",
    "a_star_b": "{a} * {b} = ? Reply with only the number.",
    "b_star_a": "{b} * {a} = ? Reply with only the number.",
    "a_groups_of_b": "What is {a} groups of {b}? Reply with only the number.",
    "b_groups_of_a": "What is {b} groups of {a}? Reply with only the number.",
}
ANCHOR_PAIR = (37, 84)


class ArithmeticRepresentation(ExperimentType):
    task_type = "arithmetic_representation"
    title = "Arithmetic representation sensitivity"
    research_question = (
        "Does the correctness of a model's answer to the same multiplication change with the surface "
        "representation of the problem (operand order, operator symbol, wording)?"
    )
    description = (
        "Each operand pair is asked in several equivalent forms. A difference between forms is an observation "
        "about this model on these prompts; it does not identify an internal cause."
    )
    default_evaluator = "numeric_match"
    fingerprint_dimension = "M"
    default_config: dict[str, Any] = {"n_random_pairs": 4, "representations": list(REPRESENTATIONS)}

    def group_of(self, variant_params: dict[str, Any]) -> str | None:
        return variant_params.get("representation")

    def block_of(self, variant_params: dict[str, Any]) -> str | None:
        pair = variant_params.get("pair")
        return f"{pair[0]}x{pair[1]}#{variant_params.get('repetition', 0)}" if pair else None

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = {**self.default_config, **config}
        reps = cfg["representations"]
        if not isinstance(reps, list) or len(reps) < 2 or any(r not in REPRESENTATIONS for r in reps):
            raise ConfigError(f"representations must be >=2 names from {sorted(REPRESENTATIONS)}")
        pairs = cfg.get("pairs")
        if pairs is not None:
            ok = isinstance(pairs, list) and pairs and all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) and 2 <= x <= 9999 for x in p)
                for p in pairs)
            if not ok:
                raise ConfigError("pairs must be a non-empty list of [a, b] integers between 2 and 9999")
        n = cfg["n_random_pairs"]
        if not isinstance(n, int) or not 0 <= n <= 50:
            raise ConfigError("n_random_pairs must be an integer between 0 and 50")
        if pairs is None and n == 0:
            cfg["pairs"] = [list(ANCHOR_PAIR)]
        return cfg

    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        cfg = self.validate_config(config)
        if cfg.get("pairs") is not None:
            pairs = [tuple(p) for p in cfg["pairs"]]
        else:
            rng = random.Random(seed)
            pairs = [ANCHOR_PAIR]
            while len(pairs) < 1 + cfg["n_random_pairs"]:
                a, b = rng.randint(12, 99), rng.randint(12, 99)
                if a != b and (a, b) not in pairs and (b, a) not in pairs:
                    pairs.append((a, b))
        items = []
        for a, b in pairs:
            for rep in cfg["representations"]:
                items.append(PromptItem(
                    prompt=REPRESENTATIONS[rep].format(a=a, b=b), expected=str(a * b),
                    variant_kind="representation", variant_label=f"{a}x{b}:{rep}",
                    variant_params={"pair": [a, b], "representation": rep},
                ))
        return items
