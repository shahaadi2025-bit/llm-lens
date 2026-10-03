"""Interval estimates for proportions and means. Every function states its method so metrics stay auditable."""
import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float
    n: int
    level: float
    method: str


def wilson_interval(successes: int, n: int, level: float = 0.95) -> Interval:
    """Wilson score interval: well-behaved for small n and for proportions near 0 or 1 (unlike the Wald interval)."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    z = float(stats.norm.ppf(0.5 + level / 2))
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), n, level, f"wilson-{int(level * 100)}")


def bootstrap_mean_interval(values: list[float], level: float = 0.95, n_boot: int = 10_000, seed: int = 0) -> Interval:
    """Percentile bootstrap CI for the mean. Seeded, so the same data always gives the same interval."""
    if len(values) < 2:
        raise ValueError("bootstrap needs at least 2 values")
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    means = arr[idx].mean(axis=1)
    alpha = (1 - level) / 2
    low, high = np.quantile(means, [alpha, 1 - alpha])
    return Interval(float(arr.mean()), float(low), float(high), len(arr), level,
                    f"bootstrap-percentile-{n_boot}-seed{seed}")
