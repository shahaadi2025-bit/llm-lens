import math

import pytest

from app.statistics.descriptive import summarize
from app.statistics.effect_sizes import cohens_d, cohens_h, correlation
from app.statistics.paired_tests import cochran_q, mcnemar_exact
from app.statistics.proportions import bootstrap_mean_interval, wilson_interval
from app.statistics.sensitivity import analyse


def test_wilson_matches_reference_values():
    i = wilson_interval(8, 10)
    assert (round(i.low, 4), round(i.high, 4)) == (0.4902, 0.9433)
    assert i.method == "wilson-95" and i.n == 10 and i.estimate == 0.8
    z = wilson_interval(0, 10)
    assert z.low == 0.0 and round(z.high, 4) == 0.2775
    o = wilson_interval(10, 10)
    assert o.high == pytest.approx(1.0) and round(o.low, 4) == 0.7225


def test_wilson_validates_input():
    for bad in [(1, 0), (-1, 5), (6, 5)]:
        with pytest.raises(ValueError):
            wilson_interval(*bad)


def test_wilson_narrows_with_more_data():
    small, big = wilson_interval(8, 10), wilson_interval(800, 1000)
    assert (big.high - big.low) < (small.high - small.low)


def test_bootstrap_is_seeded_and_brackets_mean():
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    a, b = bootstrap_mean_interval(data, seed=3), bootstrap_mean_interval(data, seed=3)
    assert (a.low, a.high) == (b.low, b.high)
    assert a.low < a.estimate == 4.5 < a.high
    with pytest.raises(ValueError):
        bootstrap_mean_interval([1.0])


def test_summarize():
    s = summarize([1, 2, 3, 4])
    assert (s.n, s.mean, s.median) == (4, 2.5, 2.5)
    assert math.isclose(s.variance, 5 / 3) and summarize([5]).variance is None
    with pytest.raises(ValueError):
        summarize([])


def test_effect_sizes_and_correlation():
    assert cohens_h(0.5, 0.5) == 0
    assert round(cohens_h(0.8, 0.5), 4) == 0.6435
    assert round(cohens_d([1, 2, 3], [3, 4, 5]), 4) == -2.0
    assert cohens_d([1], [2, 3]) is None and cohens_d([1, 1], [1, 1]) is None
    r, _ = correlation([1, 2, 3, 4], [2, 4, 6, 8])
    assert r == pytest.approx(1.0)
    assert correlation([1, 1, 1], [1, 2, 3]) is None and correlation([1, 2], [1, 2]) is None


def test_mcnemar_exact_known_value():
    a = [True] * 5 + [False] * 1 + [True] * 4
    b = [False] * 5 + [True] * 1 + [True] * 4
    r = mcnemar_exact(a, b)
    assert r.p_value == pytest.approx(0.21875)  # 2 * P(X<=1 | n=6, p=.5)
    assert mcnemar_exact([True, False], [True, False]).p_value is None


def test_cochran_q_equals_mcnemar_chi2_for_two_conditions():
    m = [[True, False]] * 6
    r = cochran_q(m)
    assert r.statistic == pytest.approx(6.0) and r.df == 1 and r.p_value == pytest.approx(0.0143, abs=1e-4)
    assert cochran_q([[True, True], [False, False]]).p_value is None
    with pytest.raises(ValueError):
        cochran_q([[True], [False]])


def test_sensitivity_flags_real_difference_but_not_mechanism():
    rows = []
    for i in range(20):  # form A always right, form B right 25% of the time, same 20 problems
        rows.append(("A", f"p{i}", True))
        rows.append(("B", f"p{i}", i % 4 == 0))
    res = analyse(rows)
    assert res.best == "A" and res.worst == "B" and res.n_blocks == 20
    assert res.cochran_p < 0.001
    text = " ".join(s.text for s in res.statements)
    assert "does not identify why" in text
    assert {s.evidence_level for s in res.statements} <= {"observation", "correlation"}  # never hypothesis/conclusion


def test_sensitivity_small_sample_refuses_to_interpret():
    res = analyse([("A", "p1", True), ("B", "p1", False), ("A", "p2", True), ("B", "p2", True)])
    assert any("too few" in s.text for s in res.statements)
    assert all(s.evidence_level == "observation" for s in res.statements)


def test_sensitivity_uniform_outcomes_and_empty():
    rows = [(g, f"p{i}", True) for i in range(12) for g in "AB"]
    assert any("no variation" in s.text for s in analyse(rows).statements)
    assert analyse([]).statements == []
