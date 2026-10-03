import warnings

import pytest

from app.clustering.embeddings import TfidfEmbedder, normalise_for_embedding
from app.clustering.kmeans import MIN_POINTS, cluster
from app.clustering.taxonomy import classify_failure


@pytest.mark.parametrize("resp,exp,expected", [
    ("", "3108", "empty_response"), ("I cannot say", "3108", "no_numeric_answer"),
    ("The answer is 3109.", "3108", "numeric_near_miss"), ("The answer is 3000.", "3108", "numeric_far_miss"),
    ("Paris", "Lyon", "wrong_text"), ("5", None, "wrong_text"), ("5", "0", "numeric_far_miss"),
])
def test_taxonomy(resp, exp, expected):
    assert classify_failure(resp, exp) == expected


def test_normalise_maps_digits():
    assert normalise_for_embedding("37 × 84 = 3108") == "00 × 00 = 0000"


def test_kmeans_separates_two_obvious_groups_and_is_seeded():
    texts = [f"form=a_x_b type=numeric_near_miss prompt=what is 00 times 00 response={i}" for i in range(8)] + \
            [f"I cannot compute that, sorry. no number here {i}" for i in range(8)]
    x = TfidfEmbedder().embed(texts)
    r1, r2 = cluster(x, len(texts), seed=3), cluster(x, len(texts), seed=3)
    assert r1 == r2 and r1.k >= 2 and r1.silhouette and r1.silhouette > 0.1
    assert len(set(r1.labels[:8])) == 1 and set(r1.labels[:8]).isdisjoint(r1.labels[8:])


def test_too_few_or_unstructured_points_stay_in_one_cluster():
    r = cluster(TfidfEmbedder().embed(["a", "b"]), 2)
    assert r.k == 1 and r.labels == [0, 0] and r.silhouette is None
    same = ["same text"] * (MIN_POINTS + 2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # sklearn warns about duplicate points; that is exactly the case under test
        assert cluster(TfidfEmbedder().embed(same), len(same)).k == 1
