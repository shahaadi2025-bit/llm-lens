"""Pick k by silhouette and cluster. Honest about structure: if nothing separates, everything stays in one cluster."""
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

MIN_POINTS = 8
MIN_AVG_CLUSTER = 4  # k is capped so clusters average >= 4 members; a silhouette score over tiny clusters is not evidence
MIN_SILHOUETTE = 0.1  # below this the 'clusters' are not distinguishable from noise


@dataclass(frozen=True)
class ClusterResult:
    labels: list[int]
    k: int
    silhouette: float | None


def cluster(x: object, n: int, seed: int = 0, max_k: int = 6) -> ClusterResult:
    if n < MIN_POINTS:
        return ClusterResult([0] * n, 1, None)
    best: tuple[float, int, np.ndarray] | None = None
    for k in range(2, min(max_k, n // MIN_AVG_CLUSTER) + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(x)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(x, labels, metric="cosine"))
        if best is None or score > best[0]:
            best = (score, k, labels)
    if best is None or best[0] < MIN_SILHOUETTE:
        return ClusterResult([0] * n, 1, best[0] if best else None)
    return ClusterResult([int(v) for v in best[2]], best[1], best[0])
