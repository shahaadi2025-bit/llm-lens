import uuid

BODY = {"name": "arith", "task_type": "arithmetic_representation", "config": {"pairs": [[37, 84]]}}


async def create(client, **over):
    r = await client.post("/api/experiments", json={**BODY, **over})
    assert r.status_code == 201, r.text
    return r.json()


async def test_experiment_types_document_research_questions(client):
    r = await client.get("/api/experiment-types")
    assert r.status_code == 200
    t = r.json()[0]
    assert t["task_type"] == "arithmetic_representation" and t["research_question"].endswith("?")


async def test_full_lifecycle_create_run_inspect(client):
    exp = await create(client)
    assert exp["status"] == "pending" and exp["counts"]["total"] == 6 and exp["is_demo_data"] is True
    assert exp["research_question"]  # defaulted from the experiment type

    r = await client.post(f"/api/experiments/{exp['id']}/run")
    assert r.status_code == 202
    await client.app_engine.wait(uuid.UUID(exp["id"]))

    d = (await client.get(f"/api/experiments/{exp['id']}")).json()
    assert d["status"] == "completed" and d["counts"]["succeeded"] == 6
    assert "DEMO / MOCK DATA" in d["notice"]
    run = d["runs"][0]
    assert run["prompt"] and run["response"] and run["evaluation"]["kind"] == "deterministic"
    assert run["expected_answer"] == "3108" and run["variant_params"]["pair"] == [37, 84]
    assert d["environment"]["python"] and d["software_version"] and d["seed"] == 0
    assert 0 <= d["counts"]["passed"] <= 6


async def test_duplicate_create_is_409_and_points_at_existing(client):
    exp = await create(client)
    r = await client.post("/api/experiments", json=BODY)
    assert r.status_code == 409 and exp["id"] in r.json()["detail"]


async def test_validation_errors(client):
    for bad in [{"temperature": 5}, {"max_tokens": 0}, {"name": ""}, {"repetitions": 999}]:
        assert (await client.post("/api/experiments", json={**BODY, **bad})).status_code == 422
    r = await client.post("/api/experiments", json={**BODY, "task_type": "nope"})
    assert r.status_code == 400 and "unknown task_type" in r.json()["detail"]
    r = await client.post("/api/experiments", json={**BODY, "config": {"pairs": [[1, 1]]}})
    assert r.status_code == 400
    r = await client.post("/api/experiments", json={**BODY, "model_slug": "gpt-9000"})
    assert r.status_code == 409


async def test_size_limit_returns_422(client):
    r = await client.post("/api/experiments", json={**BODY, "repetitions": 20, "config": {"n_random_pairs": 50}})
    assert r.status_code == 422 and "limit" in r.json()["detail"]


async def test_clone_creates_new_pending_experiment(client):
    exp = await create(client)
    r = await client.post(f"/api/experiments/{exp['id']}/clone")
    assert r.status_code == 201
    c = r.json()
    assert c["id"] != exp["id"] and c["status"] == "pending" and c["name"].endswith("(clone)")


async def test_cancel_running_then_nothing_to_cancel(client):
    exp = await create(client)
    assert (await client.post(f"/api/experiments/{exp['id']}/cancel")).json()["status"] == "cancelled"
    exp2 = await create(client, name="second", seed=1)  # name is not part of the spec hash
    await client.post(f"/api/experiments/{exp2['id']}/run")
    await client.app_engine.wait(uuid.UUID(exp2["id"]))
    r = await client.post(f"/api/experiments/{exp2['id']}/cancel")
    assert r.status_code == 409


async def test_list_filter_search(client):
    a = await create(client, name="alpha sensitivity")
    await create(client, name="beta", seed=1)
    await client.post(f"/api/experiments/{a['id']}/run")
    await client.app_engine.wait(uuid.UUID(a["id"]))
    assert len((await client.get("/api/experiments")).json()) == 2
    done = (await client.get("/api/experiments", params={"status": "completed"})).json()
    assert [e["name"] for e in done] == ["alpha sensitivity"]
    assert [e["name"] for e in (await client.get("/api/experiments", params={"q": "BETA"})).json()] == ["beta"]
    assert (await client.get("/api/experiments", params={"limit": 0})).status_code == 422


async def test_not_found_and_bad_ids(client):
    missing = uuid.uuid4()
    for method, path in [("get", f"/api/experiments/{missing}"), ("post", f"/api/experiments/{missing}/run"),
                         ("post", f"/api/experiments/{missing}/clone"), ("post", f"/api/experiments/{missing}/cancel")]:
        assert (await getattr(client, method)(path)).status_code == 404
    assert (await client.get("/api/experiments/not-a-uuid")).status_code == 422


async def test_models_and_hardware(client):
    exp = await create(client)
    models = (await client.get("/api/models")).json()
    assert len(models) == 1 and models[0]["configured"] and models[0]["is_mock"]
    assert models[0]["experiment_count"] == 1
    one = (await client.get(f"/api/models/{models[0]['id']}")).json()
    assert one["slug"] == models[0]["slug"]
    assert (await client.get(f"/api/models/{uuid.uuid4()}")).status_code == 404
    hw = (await client.get("/api/system/hardware")).json()
    assert hw["recommended_device"] in ("cpu", "cuda")
    assert exp["model_slug"] == models[0]["slug"]
