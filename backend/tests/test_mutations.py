import pytest

from app.experiments.mutations import MUTATORS, generate_mutations
from app.experiments.registry import get_experiment_type
from app.experiments.types.base import ConfigError

Q, INSTR = "What is 37 × 84?", "Reply with only the number."


def test_all_mutations_are_deterministic_and_base_comes_first():
    a, b = generate_mutations(Q, INSTR, seed=4), generate_mutations(Q, INSTR, seed=4)
    assert a == b and a[0].kind == "base" and a[0].text == f"{Q} {INSTR}"
    assert {m.kind for m in a} == set(MUTATORS)


def test_each_mutation_changes_exactly_the_described_property():
    by = {m.kind: m for m in generate_mutations(Q, INSTR)}
    assert by["uppercase"].text == f"{Q} {INSTR}".upper() and by["lowercase"].text == f"{Q} {INSTR}".lower()
    assert by["instruction_first"].text == f"{INSTR} {Q}"
    assert by["paraphrase"].text.startswith("Compute the product of 37 and 84.")
    assert by["few_shot_example"].text.endswith(f"{Q} {INSTR}") and "42" in by["few_shot_example"].text
    assert by["markdown_format"].text.startswith("**Question:**")
    assert by["irrelevant_context"].params["distractor"] in by["irrelevant_context"].text
    assert by["extra_whitespace"].text.strip() == f"{Q}\n\n\n{INSTR}"
    for m in by.values():
        assert "37" in m.text and "84" in m.text  # the problem itself is preserved


def test_irrelevant_context_depends_on_seed_but_is_reproducible():
    pick = lambda s: [m for m in generate_mutations(Q, INSTR, seed=s) if m.kind == "irrelevant_context"][0].text  # noqa: E731
    assert pick(1) == pick(1)
    assert len({pick(s) for s in range(12)}) > 1


def test_unknown_kind_and_non_multiplication_paraphrase():
    with pytest.raises(ValueError):
        generate_mutations(Q, INSTR, ["nope"])
    p = [m for m in generate_mutations("Name a colour.", INSTR) if m.kind == "paraphrase"][0]
    assert p.text == f"Name a colour. {INSTR}"  # unchanged when no template applies, and says so in params


def test_prompt_sensitivity_type_builds_grouped_items_with_one_expected_answer():
    t = get_experiment_type("prompt_sensitivity")
    items = t.build_items(t.validate_config({"n_random_pairs": 1}), 0)
    assert len(items) == 2 * 9
    assert {i.expected for i in items if i.variant_params["pair"] == [37, 84]} == {"3108"}
    assert {t.group_of(i.variant_params) for i in items} == set(MUTATORS)
    with pytest.raises(ConfigError):
        t.validate_config({"kinds": ["base"]})
    with pytest.raises(ConfigError):
        t.validate_config({"n_random_pairs": 99})
