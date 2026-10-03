"""Outlier detectors for numeric features (latency, response length, ...).

They flag POTENTIAL anomalies: unusual values, not proven failures. Each returns the indices flagged.
"""
import numpy as np
from sklearn.ensemble import IsolationForest

MIN_POINTS = 8  # below this, outlier statistics are not meaningful


def iqr_outliers(values: list[float], k: float = 1.5) -> list[int]:
    """Tukey fences: flag points beyond k * IQR from the quartiles. Needs spread (IQR > 0)."""
    if len(values) < MIN_POINTS:
        return []
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        return []
    low, high = q1 - k * iqr, q3 + k * iqr
    return [i for i, v in enumerate(values) if v < low or v > high]


def zscore_outliers(values: list[float], threshold: float = 3.0) -> list[int]:
    if len(values) < MIN_POINTS:
        return []
    arr = np.asarray(values, dtype=float)
    sd = arr.std(ddof=1)
    if sd == 0:
        return []
    z = np.abs((arr - arr.mean()) / sd)
    return [int(i) for i in np.where(z > threshold)[0]]


def isolation_forest_outliers(features: list[list[float]], contamination: float = 0.05, seed: int = 0) -> list[int]:
    """Multivariate: isolates points that are easy to separate from the rest. Seeded for reproducibility."""
    if len(features) < MIN_POINTS:
        return []
    x = np.asarray(features, dtype=float)
    if np.all(x == x[0]):
        return []
    model = IsolationForest(contamination=contamination, random_state=seed, n_estimators=100)
    labels = model.fit_predict(x)
    return [int(i) for i in np.where(labels == -1)[0]]
