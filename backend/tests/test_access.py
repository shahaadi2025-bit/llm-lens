"""Authorization: a private experiment must be invisible and untouchable to everyone except its owner,
across EVERY endpoint that exposes data derived from it."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_adapter, get_engine
from app.core.config import Settings
from app.core.db import get_session
from app.experiments.engine import ExperimentEngine
from app.main import create_app
from app.services.adapters.mock import MockAdapter

V1, V2 = "mock-deterministic-v1", "mock-deterministic-v2"
PW = "correct horse battery"
SMALL = {"name": "small", "task_type": "arithmetic_representation", "config": {"n_random_pairs": 1}, "model_slug": "mock-deterministic-v1"}
BODY = {"name": "arith", "task_type": "arithmetic_representation", "seed": 3, "config": {"n_random_pairs": 11}, "model_slug": V2}


async def signup(client, email):
    r = await client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def make(client, headers=None, **over):
    r = await client.post("/api/experiments", json={**BODY, **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def run(client, exp_id, headers=None):
    r = await client.post(f"/api/experiments/{exp_id}/run", headers=headers)
    assert r.status_code == 202, r.text
    await client.app_engine.wait(uuid.UUID(exp_id))


async def private_setup(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    exp = await make(client, alice)
    await run(client, exp["id"], alice)
    return alice, bob, exp


async def test_new_experiments_of_signed_in_users_are_private_and_owned(client):
    alice = await signup(client, "alice@example.com")
    exp = await make(client, alice)
    assert exp["is_public"] is False and exp["owned_by_me"] is True
    assert (await client.get(f"/api/experiments/{exp['id']}", headers=alice)).json()["owned_by_me"] is True


async def test_private_experiment_is_invisible_on_every_read_endpoint(client):
    alice, bob, exp = await private_setup(client)
    eid = exp["id"]
    mine = (await client.get(f"/api/experiments/{eid}/metrics", headers=alice)).json()
    metric_id = next(m["id"] for m in mine if m["name"] == "accuracy")
    fail = (await client.get("/api/failures", params={"experiment_id": eid}, headers=alice)).json()
    assert fail, "setup must produce failures to protect"
    failure_id = fail[0]["id"]

    for who, headers in (("bob", bob), ("anonymous", None)):
        for path in (f"/api/experiments/{eid}", f"/api/experiments/{eid}/metrics", f"/api/experiments/{eid}/analysis",
                     f"/api/experiments/{eid}/lineage", f"/api/metrics/{metric_id}/evidence",
                     f"/api/failures/{failure_id}/explain"):
            r = await client.get(path, headers=headers)
            assert r.status_code == 404, f"{who} could read {path}"  # 404, not 403: existence is not revealed
        assert eid not in [e["id"] for e in (await client.get("/api/experiments", headers=headers)).json()]
        assert (await client.get("/api/failures", params={"experiment_id": eid}, headers=headers)).json() == []
        dash = (await client.get("/api/dashboard", headers=headers)).json()
        assert dash["experiments_total"] == 0 and dash["potential_anomalies"] == 0 and dash["recent"] == []
    assert (await client.get("/api/dashboard", headers=alice)).json()["experiments_total"] == 1


async def test_strangers_cannot_modify_clone_or_follow_up_a_private_experiment(client):
    alice, bob, exp = await private_setup(client)
    eid = exp["id"]
    failure_id = (await client.get("/api/failures", params={"experiment_id": eid}, headers=alice)).json()[0]["id"]
    for who, headers in (("bob", bob), ("anonymous", None)):
        assert (await client.post(f"/api/experiments/{eid}/run", headers=headers)).status_code == 404, who
        assert (await client.post(f"/api/experiments/{eid}/cancel", headers=headers)).status_code == 404, who
        assert (await client.post(f"/api/experiments/{eid}/clone", headers=headers)).status_code == 404, who
        assert (await client.patch(f"/api/experiments/{eid}", json={"is_public": True}, headers=headers)).status_code == 404, who
        r = await client.post(f"/api/experiments/{eid}/follow-up", json={"failure_id": failure_id}, headers=headers)
        assert r.status_code == 404, who
    assert (await client.get(f"/api/experiments/{eid}", headers=alice)).json()["is_public"] is False  # untouched


async def test_making_public_exposes_reads_but_not_writes(client):
    alice, bob, exp = await private_setup(client)
    eid = exp["id"]
    assert (await client.patch(f"/api/experiments/{eid}", json={"is_public": True}, headers=alice)).json()["is_public"] is True
    assert (await client.get(f"/api/experiments/{eid}", headers=bob)).status_code == 200
    assert (await client.get(f"/api/experiments/{eid}/metrics", headers=None)).status_code == 200
    assert eid in [e["id"] for e in (await client.get("/api/experiments", headers=bob)).json()]
    assert (await client.get(f"/api/experiments/{eid}", headers=bob)).json()["owned_by_me"] is False
    # visible is not modifiable
    assert (await client.post(f"/api/experiments/{eid}/run", headers=bob)).status_code == 403
    assert (await client.post(f"/api/experiments/{eid}/cancel", headers=bob)).status_code == 403
    assert (await client.patch(f"/api/experiments/{eid}", json={"is_public": False}, headers=bob)).status_code == 403
    assert (await client.post(f"/api/experiments/{eid}/run")).status_code == 401  # anonymous: sign in
    # but anyone who can see it may clone it; the clone belongs to them and is private
    cl = await client.post(f"/api/experiments/{eid}/clone", headers=bob)
    assert cl.status_code == 201 and cl.json()["owned_by_me"] is True and cl.json()["is_public"] is False
    assert (await client.get(f"/api/experiments/{cl.json()['id']}", headers=alice)).status_code == 404
    # and she can make it private again
    assert (await client.patch(f"/api/experiments/{eid}", json={"is_public": False}, headers=alice)).status_code == 200
    assert (await client.get(f"/api/experiments/{eid}", headers=bob)).status_code == 404


async def test_lineage_hides_private_children_of_a_public_parent(client):
    alice, bob, exp = await private_setup(client)
    await client.patch(f"/api/experiments/{exp['id']}", json={"is_public": True}, headers=alice)
    clone = (await client.post(f"/api/experiments/{exp['id']}/clone", headers=bob)).json()
    seen_by_alice = (await client.get(f"/api/experiments/{exp['id']}/lineage", headers=alice)).json()
    assert clone["id"] not in {n["id"] for n in seen_by_alice["nodes"]} and seen_by_alice["edges"] == []
    seen_by_bob = (await client.get(f"/api/experiments/{exp['id']}/lineage", headers=bob)).json()
    assert {n["id"] for n in seen_by_bob["nodes"]} == {exp["id"], clone["id"]}


async def test_clusters_never_mix_private_data_into_shared_clusters(client):
    alice, bob, exp = await private_setup(client)
    assert (await client.post("/api/failure-clusters/recompute")).json() == []  # anonymous: nothing public to cluster
    assert (await client.post("/api/failure-clusters/recompute", headers=bob)).json() == []
    mine = (await client.post("/api/failure-clusters/recompute", headers=alice)).json()
    n_wrong = sum(1 for r in (await client.get(f"/api/experiments/{exp['id']}", headers=alice)).json()["runs"]
                  if not r["evaluation"]["passed"])
    assert mine and sum(c["size"] for c in mine) == n_wrong
    for headers in (bob, None):
        assert (await client.get("/api/failure-clusters", headers=headers)).json() == []
        assert (await client.get(f"/api/failure-clusters/{mine[0]['id']}", headers=headers)).status_code == 404
    assert len((await client.get("/api/failure-clusters", headers=alice)).json()) == len(mine)
    assert (await client.get("/api/dashboard", headers=bob)).json()["failure_clusters"] == 0
    # publishing and re-clustering as an anonymous visitor now includes it
    await client.patch(f"/api/experiments/{exp['id']}", json={"is_public": True}, headers=alice)
    shared = (await client.post("/api/failure-clusters/recompute")).json()
    assert sum(c["size"] for c in shared) == n_wrong
    await client.patch(f"/api/experiments/{exp['id']}", json={"is_public": False}, headers=alice)
    assert (await client.get("/api/failure-clusters")).json() == []  # un-publishing removes it from shared clusters at once


async def test_fingerprint_and_compare_only_use_visible_experiments(client):
    alice = await signup(client, "alice@example.com")
    bob = await signup(client, "bob@example.com")
    for slug in (V1, V2):
        e = await make(client, alice, model_slug=slug, seed=5)
        await run(client, e["id"], alice)
    versions = {v["model_slug"]: v for v in (await client.get("/api/model-versions", headers=alice)).json()}
    models = {m["slug"]: m for m in (await client.get("/api/models", headers=alice)).json()}
    fp_alice = (await client.get(f"/api/fingerprints/{models[V1]['id']}", headers=alice)).json()
    assert next(d for d in fp_alice["dimensions"] if d["code"] == "M")["measured"] is True
    for headers in (bob, None):
        fp = (await client.get(f"/api/fingerprints/{models[V1]['id']}", headers=headers)).json()
        assert not any(d["measured"] for d in fp["dimensions"])
        cmp = (await client.get("/api/compare", params={"a": versions[V1]["id"], "b": versions[V2]["id"]}, headers=headers)).json()
        assert cmp["comparable"] is False and cmp["matched"] == []
        assert next(m for m in (await client.get("/api/models", headers=headers)).json() if m["slug"] == V1)["experiment_count"] == 0
    cmp_alice = (await client.get("/api/compare", params={"a": versions[V1]["id"], "b": versions[V2]["id"]}, headers=alice)).json()
    assert cmp_alice["comparable"] is True


async def test_anonymous_sandbox_experiments_are_shared(client):
    anon = await make(client, None, seed=21)
    alice = await signup(client, "alice@example.com")
    assert (await client.get(f"/api/experiments/{anon['id']}", headers=alice)).status_code == 200
    r = await client.post(f"/api/experiments/{anon['id']}/run", headers=alice)  # sandbox: anyone may run it
    assert r.status_code == 202
    await client.app_engine.wait(uuid.UUID(anon["id"]))
    assert (await client.patch(f"/api/experiments/{anon['id']}", json={"is_public": True}, headers=alice)).status_code == 403
    assert (await client.patch(f"/api/experiments/{anon['id']}", json={"is_public": True})).status_code == 401


async def _app(engine, settings, adapter=None):
    app = create_app(settings)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    adapter = adapter or MockAdapter()

    async def sess():
        async with maker() as s:
            yield s

    eng = ExperimentEngine(maker, lambda slug: MockAdapter(slug), retry_backoff_s=0.0)
    app.dependency_overrides[get_session] = sess
    app.dependency_overrides[get_adapter] = lambda: adapter
    app.dependency_overrides[get_engine] = lambda: eng
    return app, eng


async def test_anonymous_writes_can_be_disabled(engine):
    app, _ = await _app(engine, Settings(allow_anonymous_writes=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.post("/api/experiments", json=BODY)).status_code == 401
        assert (await c.get("/api/experiments")).status_code == 200  # reading stays open
        h = await signup(c, "alice@example.com")
        assert (await c.post("/api/experiments", json=BODY, headers=h)).status_code == 201


async def test_public_mode_per_user_quota(engine):
    app, _ = await _app(engine, Settings(public_demo_mode=True, public_max_experiments_per_user=2,
                                         public_rate_limit_per_minute=1000, auth_rate_limit_per_minute=1000))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        a, b = await signup(c, "alice@example.com"), await signup(c, "bob@example.com")
        assert [(await c.post("/api/experiments", json={**SMALL, "seed": i}, headers=a)).status_code for i in (1, 2, 3)] == [201, 201, 429]
        assert (await c.post("/api/experiments", json={**SMALL, "seed": 9}, headers=b)).status_code == 201  # quota is per user


async def test_public_mode_caps_concurrent_runs(engine):
    import asyncio

    class Slow(MockAdapter):
        async def generate(self, request):
            await asyncio.sleep(0.3)
            return await super().generate(request)

    app, eng = await _app(engine, Settings(public_demo_mode=True, public_max_concurrent_experiments=1,
                                           public_rate_limit_per_minute=1000, auth_rate_limit_per_minute=1000))
    eng._adapter_provider = lambda slug: Slow(slug)  # noqa: SLF001
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        ids = []
        for seed in (1, 2):
            ids.append((await c.post("/api/experiments", json={**BODY, "seed": seed,
                                                                "config": {"n_random_pairs": 1}})).json()["id"])
        assert (await c.post(f"/api/experiments/{ids[0]}/run")).status_code == 202
        busy = await c.post(f"/api/experiments/{ids[1]}/run")
        assert busy.status_code == 429 and "busy" in busy.json()["detail"]
        await eng.wait(uuid.UUID(ids[0]))
        assert (await c.post(f"/api/experiments/{ids[1]}/run")).status_code == 202  # slot freed
        await eng.wait(uuid.UUID(ids[1]))


async def test_saved_configurations_are_private_validated_and_capped(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    body = {"name": "my setup", "task_type": "arithmetic_representation", "seed": 4, "repetitions": 2,
            "config": {"n_random_pairs": 3}}
    assert (await client.post("/api/configs", json=body)).status_code == 401  # sign-in only
    r = await client.post("/api/configs", json=body, headers=alice)
    assert r.status_code == 201 and r.json()["seed"] == 4 and r.json()["config"]["n_random_pairs"] == 3
    assert [c["name"] for c in (await client.get("/api/configs", headers=alice)).json()] == ["my setup"]
    assert (await client.get("/api/configs", headers=bob)).json() == []
    assert (await client.delete(f"/api/configs/{r.json()['id']}", headers=bob)).status_code == 404
    bad = await client.post("/api/configs", json={**body, "config": {"n_random_pairs": 999}}, headers=alice)
    assert bad.status_code == 400
    assert (await client.post("/api/configs", json={**body, "task_type": "nope"}, headers=alice)).status_code == 400
    assert (await client.delete(f"/api/configs/{r.json()['id']}", headers=alice)).status_code == 204
    assert (await client.get("/api/configs", headers=alice)).json() == []


@pytest.mark.parametrize("path", ["/api/experiments", "/api/dashboard", "/api/failures", "/api/failure-clusters",
                                  "/api/models", "/api/model-versions"])
async def test_listing_endpoints_work_anonymously_and_reject_forged_tokens(client, path):
    assert (await client.get(path)).status_code == 200
    assert (await client.get(path, headers={"Authorization": "Bearer forged.token.value"})).status_code == 401
