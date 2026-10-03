import pytest

from app.experiments.types.arithmetic import REPRESENTATIONS, ArithmeticRepresentation
from app.experiments.types.base import ConfigError

T = ArithmeticRepresentation()


def test_items_are_deterministic_for_seed():
    cfg = T.validate_config({})
    assert [i.prompt for i in T.build_items(cfg, 5)] == [i.prompt for i in T.build_items(cfg, 5)]
    assert [i.prompt for i in T.build_items(cfg, 5)] != [i.prompt for i in T.build_items(cfg, 6)]


def test_anchor_pair_uses_all_six_representations_with_same_expected():
    items = T.build_items(T.validate_config({"pairs": [[37, 84]]}), 0)
    assert len(items) == len(REPRESENTATIONS) == 6
    assert {i.expected for i in items} == {"3108"}
    assert any("84 × 37" in i.prompt for i in items) and any("37 groups of 84" in i.prompt for i in items)


def test_default_config_item_count():
    assert len(T.build_items(T.validate_config({}), 0)) == (1 + 4) * 6


@pytest.mark.parametrize("bad", [
    {"representations": ["a_x_b"]}, {"representations": ["nope", "a_x_b"]}, {"pairs": [[1, 5]]},
    {"pairs": "x"}, {"n_random_pairs": 999}, {"pairs": []},
])
def test_invalid_config_rejected(bad):
    with pytest.raises(ConfigError):
        T.validate_config(bad)
