import uuid

BODY = {"name": "arith", "task_type": "arithmetic_representation", "config": {"n_random_pairs": 11}}  # 12 pairs x 6


async def run_experiment(client, **over):
    exp = (await client.post("/api/experiments", json={**BODY, **over})).json()
    await client.post(f"/api/experiments/{exp['id']}/run")
    await client.app_engine.wait(uuid.UUID(exp["id"]))
    return exp


async def test_metrics_endpoint_and_evidence_traceability(client):
    exp = await run_experiment(client)
    ms = (await client.get(f"/api/experiments/{exp['id']}/metrics")).json()
    acc = next(m for m in ms if m["name"] == "accuracy")
    assert acc["n"] == 72 and acc["evidence_runs"] == 72 and acc["is_demo_data"] is True
    assert acc["ci_low"] <= acc["value"] <= acc["ci_high"] and acc["method"] == "wilson-95"

    ev = (await client.get(f"/api/metrics/{acc['id']}/evidence")).json()
    assert len(ev["runs"]) == 72
    r = ev["runs"][0]
    assert r["prompt"] and r["response"] and r["evaluation"]["evaluator_name"] == "numeric_match"
    # the number can be re-derived from the evidence rows
    assert sum(1 for x in ev["runs"] if x["evaluation"]["passed"]) / 72 == acc["value"]
    assert (await client.get(f"/api/metrics/{uuid.uuid4()}/evidence")).status_code == 404


async def test_analysis_never_claims_mechanism(client):
    exp = await run_experiment(client)
    a = (await client.get(f"/api/experiments/{exp['id']}/analysis")).json()
    assert len(a["groups"]) == 6 and a["n_blocks"] == 12
    assert all(g["ci_low"] <= g["accuracy"] <= g["ci_high"] and g["n"] == 12 for g in a["groups"])
    assert a["is_demo_data"] is True and a["limitations"]
    assert {s["evidence_level"] for s in a["statements"]} <= {"observation", "correlation"}
    blob = " ".join(s["text"] for s in a["statements"]).lower()
    assert "because" not in blob and "attention" not in blob


async def test_analysis_and_metrics_404_for_missing(client):
    missing = uuid.uuid4()
    assert (await client.get(f"/api/experiments/{missing}/analysis")).status_code == 404
    assert (await client.get(f"/api/experiments/{missing}/metrics")).status_code == 404


async def test_dashboard_reports_real_counts_only(client):
    empty = (await client.get("/api/dashboard")).json()
    assert empty["experiments_total"] == 0 and empty["recent"] == [] and empty["includes_demo_data"] is False
    await run_experiment(client)
    d = (await client.get("/api/dashboard")).json()
    assert d["experiments_total"] == 1 and d["experiments_completed"] == 1 and d["models_tested"] == 1
    assert d["potential_anomalies"] == 0 and d["failure_clusters"] == 0 and d["includes_demo_data"] is True
    assert d["recent"][0]["counts"]["succeeded"] == 72 and d["notes"]
