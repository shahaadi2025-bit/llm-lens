"""Tests for paired binary outcomes (the same prompt asked in several forms)."""
from dataclasses import dataclass

from scipy import stats


@dataclass(frozen=True)
class TestResult:
    name: str
    statistic: float | None
    p_value: float | None
    n_blocks: int
    df: int | None = None


def mcnemar_exact(a: list[bool], b: list[bool]) -> TestResult:
    """Exact McNemar test on discordant pairs (two conditions, same blocks)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    only_a = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    only_b = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    n = only_a + only_b
    if n == 0:
        return TestResult("mcnemar-exact", None, None, len(a))
    p = stats.binomtest(min(only_a, only_b), n, 0.5).pvalue
    return TestResult("mcnemar-exact", float(min(only_a, only_b)), float(p), len(a))


def cochran_q(matrix: list[list[bool]]) -> TestResult:
    """Cochran's Q across k conditions: rows are blocks (e.g. one problem), columns are conditions (e.g. one
    wording). Tests whether the success rate differs between conditions. Undefined if every block is all-same."""
    b = len(matrix)
    if b == 0:
        raise ValueError("no blocks")
    k = len(matrix[0])
    if k < 2 or any(len(r) != k for r in matrix):
        raise ValueError("need >=2 conditions, same count in every block")
    col = [sum(int(r[j]) for r in matrix) for j in range(k)]
    row = [sum(int(x) for x in r) for r in matrix]
    total = sum(col)
    denom = k * total - sum(r * r for r in row)
    if denom == 0:
        return TestResult("cochran-q", None, None, b, k - 1)
    q = (k - 1) * (k * sum(c * c for c in col) - total * total) / denom
    return TestResult("cochran-q", float(q), float(stats.chi2.sf(q, k - 1)), b, k - 1)
