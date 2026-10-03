import pytest

from app.anomaly.paired import find_discordant
from app.anomaly.statistical import MIN_POINTS, iqr_outliers, isolation_forest_outliers, zscore_outliers
from app.services.followup_evidence import followup_verdict

NORMAL = [10.0, 11.0, 9.5, 10.5, 10.2, 9.8, 10.1, 10.4, 9.9, 10.3]


def test_iqr_and_zscore_flag_an_extreme_point_only():
    data = [*NORMAL, 60.0]
    assert iqr_outliers(data) == [10]
    assert zscore_outliers(data, threshold=2.5) == [10]
    assert iqr_outliers(NORMAL) == [] and zscore_outliers(NORMAL) == []


def test_detectors_stay_quiet_on_tiny_or_constant_data():
    assert iqr_outliers([1.0, 100.0]) == [] and zscore_outliers([1.0] * 20) == [] and iqr_outliers([5.0] * 20) == []
    assert len([1.0] * (MIN_POINTS - 1)) < MIN_POINTS
    assert isolation_forest_outliers([[1.0, 2.0]] * 20) == []
    assert isolation_forest_outliers([[1.0, 2.0]] * 3) == []


def test_isolation_forest_finds_the_isolated_point_and_is_seeded():
    pts = [[v, v * 2] for v in NORMAL * 3] + [[500.0, 900.0]]
    a, b = isolation_forest_outliers(pts, seed=1), isolation_forest_outliers(pts, seed=1)
    assert a == b and len(pts) - 1 in a


def test_discordance_flags_failing_runs_in_mixed_blocks_only():
    cells = [("p1", "A", True, 1), ("p1", "B", False, 2), ("p1", "C", True, 3),
             ("p2", "A", False, 4), ("p2", "B", False, 5),  # all failed: hard problem, not form sensitivity
             ("p3", "A", True, 6), ("p3", "B", True, 7)]  # all passed
    out = find_discordant(cells)
    assert [(d.block, d.failed_group, d.run_id) for d in out] == [("p1", "B", 2)]
    assert out[0].passing_groups == ("A", "C")


@pytest.mark.parametrize("kf,nf,ko,no,status,strength", [
    (6, 6, 0, 30, "reproduced", "strong"),
    (5, 6, 1, 30, "reproduced", "moderate"),
    (3, 6, 0, 30, "reproduced", "weak"),
    (2, 6, 0, 30, "not_reproduced", "none"),
    (0, 6, 0, 30, "not_reproduced", "none"),
    (6, 6, 6, 6, "not_reproduced", "none"),  # everything fails: nothing specific to the form
])
def test_followup_verdict_rule(kf, nf, ko, no, status, strength):
    v = followup_verdict(kf, nf, ko, no)
    assert (v["status"], v["strength"]) == (status, strength)
    assert "Wilson" in v["rule"]
