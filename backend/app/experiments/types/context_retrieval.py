import random
from typing import Any

from app.experiments.types.base import ConfigError, ExperimentType, PromptItem

CHARS_PER_TOKEN = 4  # the same rough heuristic as ModelAdapter.estimate_tokens; sizes are approximate
HEADROOM_TOKENS = 200  # room for the question and the answer
POSITIONS = [0, 10, 25, 50, 75, 90, 100]
NAMES = ["Alder", "Birch", "Cedar", "Dogwood", "Elm", "Fir", "Hazel", "Juniper", "Maple", "Rowan", "Spruce", "Willow"]
ADJ = ["old", "quiet", "wide", "green", "narrow", "bright", "cold", "slow", "tall", "warm"]
NOUN = ["harbour", "orchard", "workshop", "meadow", "tower", "road", "market", "garden", "bridge", "station"]
VERB = ["stands", "rests", "waits", "lies", "glows", "echoes"]
PLACE = ["the river", "the hill", "the square", "the shore", "the forest", "the old wall"]


def _filler(rng: random.Random) -> str:
    return f"The {rng.choice(ADJ)} {rng.choice(NOUN)} {rng.choice(VERB)} near {rng.choice(PLACE)}."


def build_context(size_tokens: int, position_pct: int, target: str, code: str, decoys: list[tuple[str, str]], rng: random.Random) -> str:
    """Filler sentences up to ~size_tokens, with the target fact at position_pct of the sentences and decoy facts elsewhere.
    Filler contains no digits, so the only numbers in the context are the codes."""
    sentences: list[str] = []
    chars = 0
    while chars < size_tokens * CHARS_PER_TOKEN:
        s = _filler(rng)
        sentences.append(s)
        chars += len(s) + 1
    idx = round(position_pct / 100 * len(sentences))
    sentences.insert(min(idx, len(sentences)), f"The access code for vault {target} is {code}.")
    for name, c in decoys:  # decoys at random places (never replacing the target)
        sentences.insert(rng.randint(0, len(sentences)), f"The access code for vault {name} is {c}.")
    return " ".join(sentences)


class _Base(ExperimentType):
    default_evaluator = "numeric_match"
    fingerprint_dimension = "C"
    vary: str  # "position" | "length"

    def block_of(self, variant_params: dict[str, Any]) -> str | None:
        t = variant_params.get("trial")
        return None if t is None else f"trial{t}#{variant_params.get('repetition', 0)}"

    def group_of(self, variant_params: dict[str, Any]) -> str | None:
        return variant_params.get("group")

    def _common(self, cfg: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(cfg["n_trials"], int) or not 1 <= cfg["n_trials"] <= 10:
            raise ConfigError("n_trials must be an integer between 1 and 10")
        if not isinstance(cfg["n_decoys"], int) or not 0 <= cfg["n_decoys"] <= 4:
            raise ConfigError("n_decoys must be an integer between 0 and 4")
        return cfg

    def _sizes(self, cfg: dict[str, Any]) -> list[int]:
        raise NotImplementedError

    def _positions(self, cfg: dict[str, Any]) -> list[int]:
        raise NotImplementedError

    def validate_for_model(self, config: dict[str, Any], context_length: int) -> None:
        for size in self._sizes(self.validate_config(config)):
            if size + HEADROOM_TOKENS > context_length:
                raise ConfigError(f"context size {size} tokens does not fit this model's {context_length}-token window "
                                  f"(needs {size + HEADROOM_TOKENS}); unsupported sizes are never attempted")

    def build_items(self, config: dict[str, Any], seed: int) -> list[PromptItem]:
        cfg = self.validate_config(config)
        items = []
        for trial in range(cfg["n_trials"]):
            rng = random.Random(f"{seed}|ctx|{trial}")
            names = rng.sample(NAMES, 1 + cfg["n_decoys"])
            target, decoy_names = names[0], names[1:]
            code = str(rng.randint(100000, 999999))
            decoys = [(n, str(rng.randint(100000, 999999))) for n in decoy_names]
            for size in self._sizes(cfg):
                for pos in self._positions(cfg):
                    ctx = build_context(size, pos, target, code, decoys, random.Random(f"{seed}|fill|{trial}|{size}"))
                    prompt = f"{ctx}\n\nQuestion: What is the access code for vault {target}? Reply with only the number."
                    group = f"pos={pos}%" if self.vary == "position" else f"{size} tokens"
                    items.append(PromptItem(prompt=prompt, expected=code, variant_kind=self.vary,
                                            variant_label=f"trial{trial}:{group}",
                                            variant_params={"trial": trial, "group": group, "size_tokens": size,
                                                            "position_pct": pos, "target": target}))
        return items


class ContextPosition(_Base):
    task_type = "context_position"
    vary = "position"
    title = "Context-position sensitivity"
    research_question = (
        "Does the model's accuracy at retrieving a fact depend on where in a long context the fact is placed "
        "(0%, 10%, 25%, 50%, 75%, 90%, 100%)?"
    )
    description = (
        "A target fact (an access code for one named vault) is hidden among filler sentences and similar decoy facts about "
        "other vaults, at a controlled relative position. The answer is checked exactly. Context size is held fixed."
    )
    default_config: dict[str, Any] = {"size_tokens": 2000, "n_trials": 3, "n_decoys": 2}

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = self._common({**self.default_config, **config})
        if not isinstance(cfg["size_tokens"], int) or not 200 <= cfg["size_tokens"] <= 64000:
            raise ConfigError("size_tokens must be an integer between 200 and 64000")
        return cfg

    def _sizes(self, cfg: dict[str, Any]) -> list[int]:
        return [cfg["size_tokens"]]

    def _positions(self, cfg: dict[str, Any]) -> list[int]:
        return POSITIONS


class ContextLength(_Base):
    task_type = "context_length"
    vary = "length"
    title = "Context-length behavior"
    research_question = "Does the model's accuracy at retrieving a fact change as the surrounding context gets longer?"
    description = (
        "The same kind of fact is placed at the middle of contexts of increasing (approximate) token length. Sizes the "
        "chosen model cannot fit are rejected, never attempted. Latency and token use are stored per run."
    )
    default_config: dict[str, Any] = {"sizes_tokens": [500, 1000, 2000, 3000], "n_trials": 3, "n_decoys": 2}

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = self._common({**self.default_config, **config})
        s = cfg["sizes_tokens"]
        if not isinstance(s, list) or not 2 <= len(s) <= 8 or any(not isinstance(x, int) or not 200 <= x <= 64000 for x in s):
            raise ConfigError("sizes_tokens must be 2 to 8 integers between 200 and 64000")
        return cfg

    def _sizes(self, cfg: dict[str, Any]) -> list[int]:
        return sorted(set(cfg["sizes_tokens"]))

    def _positions(self, cfg: dict[str, Any]) -> list[int]:
        return [50]
