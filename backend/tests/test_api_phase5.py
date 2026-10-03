import uuid

import pytest

BODY = {"name": "arith", "task_type": "arithmetic_representation", "seed": 3, "config": {"n_random_pairs": 11}}
V1, V2 = "mock-deterministic-v1", "mock-deterministic-v2"


async def run(client, exp_id):
    assert (await client.post(f"/api/experiments/{exp_id}/run")).status_code == 202
    await client.app_engine.wait(uuid.UUID(exp_id))


async def make(client, model=V1, **over):
    r = await client.post("/api/experiments", json={**BODY, "model_slug": model, **over})
    assert r.status_code == 201, r.text
    await run(client, r.json()["id"])
    return r.json()


async def versions(client):
    await client.get("/api/models")  # registers both mock models
    vs = (await client.get("/api/model-versions")).json()
    return {v["model_slug"]: v for v in vs}


async def test_model_selection_runs_the_chosen_mock_version(client):
    e1, e2 = await make(client, V1), await make(client, V2)
    assert (e1["model_slug"], e1["model_version"]) == (V1, "mock-1") and (e2["model_slug"], e2["model_version"]) == (V2, "mock-2")
    assert (await client.post("/api/experiments", json={**BODY, "model_slug": "gpt-9000", "seed": 99})).status_code == 409


async def test_clustering_groups_incorrect_answers_and_traces_them(client):
    exp = await make(client, V2)  # higher error rate -> plenty of failures
    cs = (await client.post("/api/failure-clusters/recompute")).json()
    assert cs and all(c["size"] > 0 and c["includes_demo_data"] and "not why" in c["note"] for c in cs)
    detail = (await client.get(f"/api/failure-clusters/{cs[0]['id']}")).json()
    assert len(detail["members"]) == detail["size"]
    m = detail["members"][0]
    assert m["status"] == "observed_incorrect" and m["response"] and m["can_follow_up"] is False
    ex = (await client.get(f"/api/failures/{m['id']}/explain")).json()  # members can be explained like any other failure
    assert "incorrect" in ex["observed"] and ex["demo_notice"]
    n_wrong = sum(1 for r in (await client.get(f"/api/experiments/{exp['id']}")).json()["runs"] if not r["evaluation"]["passed"])
    assert sum(c["size"] for c in cs) == n_wrong  # every incorrect answer lands in exactly one cluster
    assert (await client.get("/api/dashboard")).json()["failure_clusters"] == len(cs)
    again = (await client.post("/api/failure-clusters/recompute")).json()  # idempotent
    assert sum(c["size"] for c in again) == n_wrong and len((await client.get("/api/failure-clusters")).json()) == len(again)
    assert (await client.get(f"/api/failure-clusters/{uuid.uuid4()}")).status_code == 404


async def test_clustering_with_no_failures_is_empty(client):
    assert (await client.post("/api/failure-clusters/recompute")).json() == []


async def test_rerunning_detection_keeps_cluster_membership(client):
    exp = await make(client, V2)
    cs = (await client.post("/api/failure-clusters/recompute")).json()
    await client.app_engine.wait(uuid.UUID(exp["id"]))
    from app.services.anomalies import detect_and_store  # noqa: F401  (detector rerun must not delete cluster rows)
    assert len((await client.get("/api/failure-clusters")).json()) == len(cs)


async def test_fingerprint_measured_vs_unmeasured_and_traceable(client):
    exp = await make(client, V1)
    vs = await versions(client)
    fp = (await client.get(f"/api/fingerprints/{vs[V1]['model_id']}")).json()
    assert fp["includes_demo_data"] is True and len(fp["dimensions"]) == 8
    dims = {d["code"]: d for d in fp["dimensions"]}
    assert dims["M"]["measured"] and dims["M"]["n"] == 72 and dims["M"]["ci_low"] <= dims["M"]["value"] <= dims["M"]["ci_high"]
    assert dims["M"]["metrics"][0]["experiment_id"] == exp["id"]
    for code in "RFCIHTS":
        assert dims[code]["measured"] is False and dims[code]["value"] is None  # unmeasured is not zero
    assert (await client.get(f"/api/metrics/{dims['M']['metrics'][0]['metric_id']}/evidence")).status_code == 200
    other = (await client.get(f"/api/fingerprints/{vs[V2]['model_id']}")).json()
    assert not any(d["measured"] for d in other["dimensions"])
    assert (await client.get(f"/api/fingerprints/{uuid.uuid4()}")).status_code == 404


async def test_compare_matched_designs_never_asserts_a_cause(client):
    await make(client, V1)
    await make(client, V2)
    vs = await versions(client)
    r = (await client.get("/api/compare", params={"a": vs[V1]["id"], "b": vs[V2]["id"]})).json()
    assert r["comparable"] and r["includes_demo_data"] and len(r["matched"]) == 1
    acc = next(d for d in r["differences"] if d["metric"] == "accuracy")
    assert acc["a_n"] == acc["b_n"] == 72 and acc["diff_ci_low"] <= acc["difference"] <= acc["diff_ci_high"]
    assert acc["difference"] < 0  # v2 injects more errors than v1
    assert acc["paired_only_a"] is not None and acc["mcnemar_p"] is not None
    assert "does not say what changed" in acc["statement"] or "compatible with no difference" in acc["statement"]
    assert "DEMO" in acc["statement"]
    assert not any(w in acc["statement"].lower() for w in ("because", "caused", "due to"))


async def test_compare_unmatched_designs_and_errors(client):
    await make(client, V1)
    await make(client, V2, seed=11)  # different seed -> different design: not comparable
    vs = await versions(client)
    r = (await client.get("/api/compare", params={"a": vs[V1]["id"], "b": vs[V2]["id"]})).json()
    assert r["comparable"] is False and r["differences"] == [] and r["unmatched_a"] and r["unmatched_b"]
    assert (await client.get("/api/compare", params={"a": vs[V1]["id"], "b": vs[V1]["id"]})).status_code == 422
    assert (await client.get("/api/compare", params={"a": vs[V1]["id"], "b": str(uuid.uuid4())})).status_code == 404


def test_newcombe_difference_reference():
    from app.statistics.proportions import newcombe_difference

    # 56/70 vs 48/80. Wilson bounds: [0.6918, 0.8770] and [0.4905, 0.7004]. Hand calculation of the hybrid-score formula:
    # low = -0.2 - sqrt(0.0770^2 + 0.1095^2) = -0.3339 ; high = -0.2 + sqrt(0.1082^2 + 0.1004^2) = -0.0524
    d, lo, hi = newcombe_difference(56, 70, 48, 80)
    assert d == pytest.approx(-0.2) and lo == pytest.approx(-0.3339, abs=5e-4) and hi == pytest.approx(-0.0524, abs=5e-4)
    d0, lo0, hi0 = newcombe_difference(5, 10, 5, 10)
    assert d0 == 0 and lo0 < 0 < hi0
