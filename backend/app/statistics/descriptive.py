import statistics as pystats
from dataclasses import dataclass


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    median: float
    variance: float | None  # sample variance (n-1); None when n < 2
    std: float | None


def summarize(values: list[float]) -> Summary:
    if not values:
        raise ValueError("no values")
    n = len(values)
    var = pystats.variance(values) if n > 1 else None
    return Summary(n, pystats.fmean(values), pystats.median(values), var, var**0.5 if var is not None else None)
