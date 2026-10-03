import math

import numpy as np
from scipy import stats


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for a difference between two proportions (arcsine transform). |h| ~0.2 small, 0.5 medium, 0.8 large."""
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def cohens_d(a: list[float], b: list[float]) -> float | None:
    """Standardised mean difference with pooled SD. None when it is undefined."""
    if len(a) < 2 or len(b) < 2:
        return None
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return None if pooled == 0 else (float(np.mean(a)) - float(np.mean(b))) / pooled


def correlation(x: list[float], y: list[float], method: str = "spearman") -> tuple[float, float] | None:
    """(coefficient, p-value). Spearman by default (rank-based, robust). None if undefined (constant input, n<3)."""
    if len(x) != len(y) or len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    fn = {"spearman": stats.spearmanr, "pearson": stats.pearsonr}[method]
    r = fn(x, y)
    return float(r[0]), float(r[1])
