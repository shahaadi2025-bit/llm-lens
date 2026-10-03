import uuid

BODY = {"name": "arith", "task_type": "arithmetic_representation", "config": {"n_random_pairs": 11}}  # 72 runs


async def run(client, exp_id):
    r = await client.post(f"/api/experiments/{exp_id}/run")
    assert r.status_code == 202, r.text
    await client.app_engine.wait(uuid.UUID(exp_id))


async def make_and_run(client, **over):
    exp = (await client.post("/api/experiments", json={**BODY, **over})).json()
    await run(client, exp["id"])
    return exp


async def paired_failures(client, exp_id):
    fs = (await client.get("/api/failures", params={"experiment_id": exp_id, "label": "representation_sensitivity"})).json()
    return fs


async def test_detection_flags_potential_anomalies_not_failures(client):
    exp = await make_and_run(client)
    fs = await paired_failures(client, exp["id"])
    assert fs, "the mock injects ~15% wrong answers, so some discordant blocks must exist"
    for f in fs:
        assert f["status"] == "potential_anomaly" and f["detector"] == "paired_discordance"
        assert f["details"]["passing_groups"] and f["details"]["failed_group"] and f["is_demo_data"] is True
        assert f["prompt"] and f["can_follow_up"] is True
    # a flagged run really was answered incorrectly
    detail = (await client.get(f"/api/experiments/{exp['id']}")).json()
    wrong = {r["id"] for r in detail["runs"] if not r["evaluation"]["passed"]}
    assert {f["run_id"] for f in fs} <= wrong
    assert (await client.get("/api/dashboard")).json()["potential_anomalies"] >= len(fs)


async def test_follow_up_flow_updates_evidence_and_explain(client):
    exp = await make_and_run(client)
    f = (await paired_failures(client, exp["id"]))[0]

    r = await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": f["id"]})
    assert r.status_code == 201, r.text
    child = r.json()
    assert child["status"] == "pending" and child["counts"]["total"] == 36  # 1 pair x 6 forms x 6 seeds
    assert child["task_type"] == "arithmetic_representation" and child["seed"] == 1000

    before = (await client.get(f"/api/failures/{f['id']}/explain")).json()
    assert before["evidence"]["strength"] == "none" and before["evidence"]["level"] == "observation"
    assert "No completed follow-up" in before["evidence"]["summary"]

    await run(client, child["id"])
    after = (await client.get(f"/api/failures/{f['id']}/explain")).json()
    assert after["failure"]["status"] in ("reproduced", "not_reproduced")
    assert after["follow_ups"][0]["experiment_id"] == child["id"] and after["follow_ups"][0]["summary"]
    assert after["evidence"]["status"] == after["failure"]["status"]
    assert after["evidence"]["level"] in ("observation", "correlation")  # never an unearned 'supported conclusion'


async def test_explain_never_asserts_a_mechanism_and_labels_mock(client):
    exp = await make_and_run(client)
    f = (await paired_failures(client, exp["id"]))[0]
    e = (await client.get(f"/api/failures/{f['id']}/explain")).json()
    assert e["demo_notice"] and "DEMO / MOCK DATA" in e["demo_notice"]
    assert e["observed"] and e["controlled_variables"] and e["changed_variable"] and e["limitations"]
    assert e["alternative_explanations"]  # chance and evaluator artifact are always on the table
    assert all(s["evidence_level"] == "hypothesis" for s in e["possible_explanations"] + e["alternative_explanations"])
    text = " ".join([e["observed"], *[s["text"] for s in e["possible_explanations"]]]).lower()
    for banned in ("attention", "because the model", "neuron", "weights"):
        assert banned not in text
    assert any("does not" in lim.lower() or "can show that" in lim.lower() for lim in e["limitations"])


async def test_lineage_links_parent_and_follow_up(client):
    exp = await make_and_run(client)
    f = (await paired_failures(client, exp["id"]))[0]
    child = (await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": f["id"]})).json()
    lin = (await client.get(f"/api/experiments/{child['id']}/lineage")).json()
    assert {n["id"] for n in lin["nodes"]} == {exp["id"], child["id"]}
    assert sum(n["is_current"] for n in lin["nodes"]) == 1
    edge = lin["edges"][0]
    assert (edge["parent"], edge["child"], edge["relation"]) == (exp["id"], child["id"], "follow_up")
    assert edge["trigger_run_id"] == f["run_id"] and edge["note"].startswith("Hypothesis (untested)")


async def test_follow_up_error_cases(client):
    exp = await make_and_run(client)
    f = (await paired_failures(client, exp["id"]))[0]
    other = (await client.post("/api/experiments", json={**BODY, "seed": 5})).json()
    assert (await client.post(f"/api/experiments/{other['id']}/follow-up", json={"failure_id": f["id"]})).status_code == 422
    assert (await client.post(f"/api/experiments/{uuid.uuid4()}/follow-up", json={"failure_id": f["id"]})).status_code == 404
    assert (await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": str(uuid.uuid4())})).status_code == 404
    first = await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": f["id"]})
    assert first.status_code == 201
    dup = await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": f["id"]})
    assert dup.status_code == 409  # identical follow-up already exists
    assert (await client.get(f"/api/failures/{uuid.uuid4()}/explain")).status_code == 404
    assert (await client.get(f"/api/experiments/{uuid.uuid4()}/lineage")).status_code == 404


async def test_statistical_outliers_have_no_follow_up(client):
    exp = await make_and_run(client)
    stat = (await client.get("/api/failures", params={"experiment_id": exp["id"], "label": "statistical_outlier"})).json()
    if stat:  # outliers on mock latency are timing noise; whenever present they must refuse a follow-up
        assert stat[0]["can_follow_up"] is False
        r = await client.post(f"/api/experiments/{exp['id']}/follow-up", json={"failure_id": stat[0]["id"]})
        assert r.status_code == 422


async def test_prompt_sensitivity_end_to_end(client):
    body = {"name": "ps", "task_type": "prompt_sensitivity", "config": {"n_random_pairs": 3}}  # 4 pairs x 9 forms = 36
    exp = (await client.post("/api/experiments", json=body)).json()
    assert exp["counts"]["total"] == 36
    await run(client, exp["id"])
    ms = (await client.get(f"/api/experiments/{exp['id']}/metrics")).json()
    acc = next(m for m in ms if m["name"] == "accuracy")
    assert acc["dimension"] == "S" and sum(m["name"].startswith("accuracy[") for m in ms) == 9
    a = (await client.get(f"/api/experiments/{exp['id']}/analysis")).json()
    assert len(a["groups"]) == 9 and a["n_blocks"] == 4
