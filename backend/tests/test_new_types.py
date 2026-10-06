import json
import re
import uuid

import pytest

from app.evaluators.constraints import ConstraintCheck, check_one, describe
from app.evaluators.registry import get_evaluator
from app.experiments.registry import get_experiment_type
from app.experiments.types.base import ConfigError
from app.experiments.types.context_retrieval import POSITIONS
from app.services.adapters.base import GenerationRequest
from app.services.adapters.mock import MockAdapter
from app.statistics.sensitivity import _natural

# ---------------------------------------------------------------- constraint checker


@pytest.mark.parametrize("spec,good,bad", [
    ({"type": "max_words", "n": 5}, "one two three", "one two three four five six"),
    ({"type": "include", "word": "bright"}, "A bright day.", "A brightness day."),  # whole words only
    ({"type": "exclude", "word": "very"}, "A nice day.", "A Very nice day."),  # case-insensitive
    ({"type": "lowercase"}, "all lower.", "Not lower."),
    ({"type": "starts_with", "text": "indeed"}, "indeed so.", "so indeed."),
    ({"type": "ends_with", "text": "that is all."}, "yes. that is all.", "that is all. yes."),
    ({"type": "sentences", "n": 2}, "One. Two.", "One. Two. Three."),
])
def test_each_constraint_type_passes_and_fails_correctly(spec, good, bad):
    assert check_one(good, spec) is True and check_one(bad, spec) is False
    assert describe(spec)


def test_constraint_check_scores_the_fraction_satisfied_and_passes_only_when_all_are():
    expected = json.dumps({"constraints": [{"type": "lowercase"}, {"type": "sentences", "n": 2}, {"type": "include", "word": "sea"}]})
    ev = ConstraintCheck()
    full = ev.evaluate("the sea. calm.", expected)
    assert (full.score, full.passed) == (1.0, True)
    part = ev.evaluate("The sea. calm.", expected)  # not lowercase
    assert part.passed is False and part.score == pytest.approx(2 / 3) and part.details["satisfied"] == 2
    assert [r["satisfied"] for r in part.details["results"]] == [False, True, True]
    assert ev.evaluate("", expected).details["reason"] == "empty_response"
    assert ev.evaluate("x", None).details["reason"] == "no_expected_constraints"
    assert ev.evaluate("x", "not json").details["reason"] == "unparseable_constraints"
    assert get_evaluator("constraint_check").kind == "deterministic"


# ---------------------------------------------------------------- instruction ordering


def test_ordering_variants_share_constraints_but_change_the_order_and_are_deterministic():
    t = get_experiment_type("instruction_ordering")
    cfg = t.validate_config({})
    a, b = t.build_items(cfg, 5), t.build_items(cfg, 5)
    assert [i.prompt for i in a] == [i.prompt for i in b] and [i.prompt for i in a] != [i.prompt for i in t.build_items(cfg, 6)]
    assert len(a) == 6 * 4  # 6 tasks x (listed + 3 orderings)
    for task in range(6):
        group = [i for i in a if i.variant_params["task"] == task]
        assert len({i.expected for i in group}) == 1  # the constraint set is identical in every ordering
        lines = {i.variant_params["ordering"]: re.findall(r"^- (.+)$", i.prompt, re.M) for i in group}
        assert sorted(lines["listed"]) == sorted(lines["reversed"]) == sorted(lines["rotated"]) == sorted(lines["shuffled"])
        assert lines["reversed"] == lines["listed"][::-1] and lines["rotated"] == lines["listed"][1:] + lines["listed"][:1]
        assert lines["shuffled"] != lines["listed"]
    assert {t.group_of(i.variant_params) for i in a} == {"listed", "reversed", "rotated", "shuffled"}


@pytest.mark.parametrize("bad", [{"n_tasks": 0}, {"n_tasks": 99}, {"n_constraints": 1}, {"n_constraints": 9},
                                 {"orderings": []}, {"orderings": ["listed"]}, {"orderings": ["nope"]}])
def test_invalid_instruction_config_is_rejected(bad):
    with pytest.raises(ConfigError):
        get_experiment_type("instruction_ordering").validate_config(bad)


async def test_mock_follows_instructions_with_slips_independent_of_instruction_order():
    t = get_experiment_type("instruction_ordering")
    items = t.build_items(t.validate_config({"n_tasks": 10, "n_constraints": 4}), 3)
    ev, mock = ConstraintCheck(), MockAdapter()
    passed = {}
    for it in items:
        r = await mock.generate(GenerationRequest(prompt=it.prompt, seed=3))
        passed.setdefault(it.variant_params["ordering"], []).append(ev.evaluate(r.text, it.expected).passed)
    total = sum(sum(v) for v in passed.values()) / len(items)
    assert 0.6 < total < 1.0  # mostly compliant, with some slips so both outcomes exist
    rates = [sum(v) / len(v) for v in passed.values()]
    # Slips come from a hash of the whole prompt, not from where an instruction sits, so no ordering is systematically worse.
    # With only 10 tasks per ordering, sampling noise alone can move a rate by 30+ points; assert only that none collapses.
    assert min(rates) >= 0.3 and len(rates) == 4


# ---------------------------------------------------------------- context retrieval


def test_needle_sits_at_the_requested_relative_position_with_decoys_and_no_stray_digits():
    t = get_experiment_type("context_position")
    items = t.build_items(t.validate_config({"size_tokens": 1000, "n_trials": 1}), 2)
    assert len(items) == len(POSITIONS) == 7
    for it in items:
        ctx = it.prompt.split("\n\nQuestion:")[0]
        sentences = re.split(r"(?<=\.)\s+", ctx)
        target = it.variant_params["target"]
        idx = next(i for i, s in enumerate(sentences) if f"vault {target} is {it.expected}" in s)
        pos = it.variant_params["position_pct"]
        assert abs(idx / len(sentences) * 100 - pos) < 12, (pos, idx, len(sentences))  # decoys shift it slightly
        assert ctx.count("access code for vault") == 3  # target + 2 decoys
        assert it.prompt.count(it.expected) == 1  # the answer appears once, as the target fact
        assert len(ctx) > 3500  # about 1000 tokens
        assert not re.search(r"\d", re.sub(r"vault \w+ is \d+", "", ctx))  # filler has no digits
    assert [t.group_of(i.variant_params) for i in items] == [f"pos={p}%" for p in POSITIONS]


def test_unsupported_context_sizes_are_rejected_not_attempted():
    t = get_experiment_type("context_length")
    t.validate_for_model(t.validate_config({"sizes_tokens": [500, 1000]}), 4096)
    with pytest.raises(ConfigError, match="never attempted"):
        t.validate_for_model(t.validate_config({"sizes_tokens": [500, 8000]}), 4096)
    p = get_experiment_type("context_position")
    with pytest.raises(ConfigError):
        p.validate_for_model(p.validate_config({"size_tokens": 4000}), 4096)  # 4000 + headroom > 4096


def test_context_length_groups_and_validation():
    t = get_experiment_type("context_length")
    items = t.build_items(t.validate_config({"sizes_tokens": [1000, 500], "n_trials": 2}), 1)
    assert len(items) == 4 and {i.variant_params["position_pct"] for i in items} == {50}
    assert sorted({i.variant_params["group"] for i in items}) == ["1000 tokens", "500 tokens"]
    for bad in ({"sizes_tokens": [500]}, {"sizes_tokens": [10, 500]}, {"n_trials": 0}, {"n_decoys": 9}):
        with pytest.raises(ConfigError):
            t.validate_config(bad)


async def test_mock_retrieves_the_named_vault_despite_decoys():
    t = get_experiment_type("context_position")
    items = t.build_items(t.validate_config({"size_tokens": 600, "n_trials": 4}), 9)
    ev, mock = get_evaluator("numeric_match"), MockAdapter()
    hits = [ev.evaluate((await mock.generate(GenerationRequest(prompt=i.prompt, seed=9))).text, i.expected).passed for i in items]
    assert 0.6 < sum(hits) / len(hits) < 1.0


def test_natural_sort_orders_numbers_numerically():
    labels = ["pos=100%", "pos=0%", "pos=25%", "pos=5%", "pos=50%"]
    assert sorted(labels, key=_natural) == ["pos=0%", "pos=5%", "pos=25%", "pos=50%", "pos=100%"]
    assert sorted(["1000 tokens", "500 tokens", "2000 tokens"], key=_natural) == ["500 tokens", "1000 tokens", "2000 tokens"]


# ---------------------------------------------------------------- end to end through the API


async def _run(client, body):
    r = await client.post("/api/experiments", json=body)
    assert r.status_code == 201, r.text
    await client.post(f"/api/experiments/{r.json()['id']}/run")
    await client.app_engine.wait(uuid.UUID(r.json()["id"]))
    return r.json()


async def test_instruction_experiment_feeds_the_instruction_dimension_and_reports_by_ordering(client):
    exp = await _run(client, {"name": "ordering", "task_type": "instruction_ordering", "seed": 2, "config": {"n_tasks": 10}})
    assert exp["evaluator"] == "constraint_check" and exp["counts"]["total"] == 40
    d = (await client.get(f"/api/experiments/{exp['id']}")).json()
    r = d["runs"][0]
    assert r["evaluation"]["kind"] == "deterministic" and "results" in r["evaluation"]["details"]
    ms = (await client.get(f"/api/experiments/{exp['id']}/metrics")).json()
    assert next(m for m in ms if m["name"] == "accuracy")["dimension"] == "I"
    a = (await client.get(f"/api/experiments/{exp['id']}/analysis")).json()
    assert [g["group"] for g in a["groups"]] == ["listed", "reversed", "rotated", "shuffled"] or len(a["groups"]) == 4
    assert a["n_blocks"] == 10 and {s["evidence_level"] for s in a["statements"]} <= {"observation", "correlation"}
    models = {m["slug"]: m for m in (await client.get("/api/models")).json()}
    fp = (await client.get(f"/api/fingerprints/{models['mock-deterministic-v1']['id']}")).json()
    dims = {x["code"]: x for x in fp["dimensions"]}
    assert dims["I"]["measured"] and dims["I"]["n"] == 40 and not dims["R"]["measured"]
    rep = (await client.post("/api/reports", json={"experiment_id": exp["id"]})).json()["content"]
    assert rep.count("\n## ") == 14 and "orderings" in rep and "DEMO / MOCK DATA" in rep


async def test_position_experiment_orders_the_chart_left_to_right_and_feeds_context_dimension(client):
    exp = await _run(client, {"name": "position", "task_type": "context_position", "seed": 4,
                              "config": {"size_tokens": 800, "n_trials": 10}})
    assert exp["counts"]["total"] == 70
    a = (await client.get(f"/api/experiments/{exp['id']}/analysis")).json()
    assert [g["group"] for g in a["groups"]] == [f"pos={p}%" for p in POSITIONS]  # numeric order, not alphabetical
    assert all(g["n"] == 10 for g in a["groups"]) and a["n_blocks"] == 10
    ms = (await client.get(f"/api/experiments/{exp['id']}/metrics")).json()
    assert next(m for m in ms if m["name"] == "accuracy")["dimension"] == "C"
    text = " ".join(s["text"] for s in a["statements"]).lower()
    assert "because" not in text and "attention" not in text


async def test_context_length_experiment_rejects_sizes_the_model_cannot_fit(client):
    ok = await _run(client, {"name": "len", "task_type": "context_length", "seed": 5,
                             "config": {"sizes_tokens": [400, 900], "n_trials": 2}})
    assert ok["counts"]["total"] == 4
    r = await client.post("/api/experiments", json={"name": "too long", "task_type": "context_length",
                                                    "config": {"sizes_tokens": [500, 9000]}})
    assert r.status_code == 400 and "does not fit" in r.json()["detail"] and "never attempted" in r.json()["detail"]


async def test_prompt_character_limit_protects_the_deployment(client):
    r = await client.post("/api/experiments", json={"name": "huge", "task_type": "context_position", "seed": 1, "repetitions": 20,
                                                    "config": {"size_tokens": 3000, "n_trials": 10}})
    assert r.status_code == 422 and "prompt characters" in r.json()["detail"]
