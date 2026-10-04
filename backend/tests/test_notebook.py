import uuid

PW = "correct horse battery"
BODY = {"name": "arith", "task_type": "arithmetic_representation", "seed": 3, "config": {"n_random_pairs": 3},
        "model_slug": "mock-deterministic-v1"}


async def signup(client, email):
    r = await client.post("/api/auth/register", json={"email": email, "password": PW})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def experiment(client, headers, **over):
    r = await client.post("/api/experiments", json={**BODY, **over}, headers=headers)
    assert r.status_code == 201, r.text
    await client.post(f"/api/experiments/{r.json()['id']}/run", headers=headers)
    await client.app_engine.wait(uuid.UUID(r.json()["id"]))
    return r.json()


async def inv(client, headers, **over):
    r = await client.post("/api/investigations", json={"title": "Does form matter?", "research_question": "Q?",
                                                       "hypothesis": "H.", **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_notebook_requires_sign_in_and_is_private(client):
    assert (await client.get("/api/investigations")).status_code == 401
    assert (await client.post("/api/investigations", json={"title": "x"})).status_code == 401
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    i = await inv(client, alice)
    assert [x["id"] for x in (await client.get("/api/investigations", headers=alice)).json()] == [i["id"]]
    assert (await client.get("/api/investigations", headers=bob)).json() == []
    base = f"/api/investigations/{i['id']}"
    attempts = (("get", base, {}), ("patch", base, {"json": {"title": "x"}}), ("delete", base, {}),
                ("post", f"{base}/notes", {"json": {"kind": "note", "text": "x"}}))
    for method, path, kw in attempts:
        assert (await getattr(client, method)(path, headers=bob, **kw)).status_code == 404, (method, path)


async def test_conclusion_requires_limitations(client):
    alice = await signup(client, "alice@example.com")
    i = await inv(client, alice)
    url = f"/api/investigations/{i['id']}"
    r = await client.patch(url, json={"conclusion": "Form matters."}, headers=alice)
    assert r.status_code == 422 and "limitations" in r.json()["detail"].lower()
    assert (await client.get(url, headers=alice)).json()["conclusion"] == ""  # nothing was saved
    ok = await client.patch(url, json={"conclusion": "Form seems to matter here.", "limitations": "Mock model; 3 problems."}, headers=alice)
    assert ok.status_code == 200 and ok.json()["conclusion"] and ok.json()["limitations"]
    # Stripping the limitations from a standing conclusion is refused, and the stored value is untouched.
    stripped = await client.patch(url, json={"limitations": ""}, headers=alice)
    assert stripped.status_code == 422
    assert (await client.get(url, headers=alice)).json()["limitations"] == "Mock model; 3 problems."
    # Clearing both together is allowed.
    cleared = await client.patch(url, json={"conclusion": "", "limitations": ""}, headers=alice)
    assert cleared.status_code == 200 and cleared.json()["conclusion"] == ""


async def test_notes_validation_and_deletion(client):
    alice = await signup(client, "alice@example.com")
    i = await inv(client, alice)
    url = f"/api/investigations/{i['id']}/notes"
    assert (await client.post(url, json={"kind": "conclusion", "text": "x"}, headers=alice)).status_code == 422  # not a note kind
    assert (await client.post(url, json={"kind": "note", "text": ""}, headers=alice)).status_code == 422
    d = (await client.post(url, json={"kind": "observation", "text": "37x84 failed once"}, headers=alice)).json()
    assert [n["kind"] for n in d["notes"]] == ["observation"]
    nid = d["notes"][0]["id"]
    assert (await client.delete(f"{url}/{nid}", headers=alice)).json()["notes"] == []


async def test_link_experiments_respects_visibility(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    mine = await experiment(client, alice)
    i = await inv(client, bob)
    url = f"/api/investigations/{i['id']}/experiments"
    assert (await client.post(url, json={"experiment_id": mine["id"]}, headers=bob)).status_code == 404  # alice's private one
    await client.patch(f"/api/experiments/{mine['id']}", json={"is_public": True}, headers=alice)
    d = (await client.post(url, json={"experiment_id": mine["id"]}, headers=bob)).json()
    assert [e["id"] for e in d["experiments"]] == [mine["id"]] and d["hidden_experiments"] == 0
    again = (await client.post(url, json={"experiment_id": mine["id"]}, headers=bob)).json()
    assert len(again["experiments"]) == 1  # linking twice is harmless
    await client.patch(f"/api/experiments/{mine['id']}", json={"is_public": False}, headers=alice)  # alice un-publishes
    gone = (await client.get(f"/api/investigations/{i['id']}", headers=bob)).json()
    assert gone["experiments"] == [] and gone["hidden_experiments"] == 1  # no leak, but the link is acknowledged
    assert (await client.post(url, json={"experiment_id": str(uuid.uuid4())}, headers=bob)).status_code == 404
    assert (await client.delete(f"{url}/{mine['id']}", headers=bob)).json()["hidden_experiments"] == 0


async def test_investigation_report_is_owner_only_and_uses_the_researchers_words(client):
    alice, bob = await signup(client, "alice@example.com"), await signup(client, "bob@example.com")
    e = await experiment(client, alice)
    i = await inv(client, alice)
    base = f"/api/investigations/{i['id']}"
    await client.post(f"{base}/experiments", json={"experiment_id": e["id"]}, headers=alice)
    await client.post(f"{base}/notes", json={"kind": "observation", "text": "Accuracy was high overall."}, headers=alice)
    await client.post(f"{base}/notes", json={"kind": "hypothesis", "text": "Try irrelevant context next."}, headers=alice)
    await client.patch(base, json={"conclusion": "Nothing conclusive yet.", "limitations": "Only 4 problems; mock model."}, headers=alice)
    rep = await client.post("/api/reports", json={"investigation_id": i["id"]}, headers=alice)
    assert rep.status_code == 201
    c = rep.json()["content"]
    for needle in ("# Investigation report: Does form matter?", "## Research question", "Accuracy was high overall.",
                   "Try irrelevant context next.", "Nothing conclusive yet.", "Only 4 problems; mock model.", e["id"],
                   "DEMO / MOCK DATA"):
        assert needle in c, needle
    assert "cannot establish internal mechanisms" in c
    rid = rep.json()["id"]
    assert (await client.get(f"/api/reports/{rid}", headers=bob)).status_code == 404
    assert (await client.get(f"/api/reports/{rid}")).status_code == 404
    assert (await client.post("/api/reports", json={"investigation_id": i["id"]}, headers=bob)).status_code == 404
    assert rid not in [r["id"] for r in (await client.get("/api/reports", headers=bob)).json()]
    assert rid in [r["id"] for r in (await client.get("/api/reports", headers=alice)).json()]


async def test_empty_conclusion_is_stated_not_invented(client):
    alice = await signup(client, "alice@example.com")
    i = await inv(client, alice)
    c = (await client.post("/api/reports", json={"investigation_id": i["id"]}, headers=alice)).json()["content"]
    assert "No conclusion has been recorded." in c and "No limitations have been recorded." in c


async def test_delete_investigation_removes_it(client):
    alice = await signup(client, "alice@example.com")
    i = await inv(client, alice)
    await client.post(f"/api/investigations/{i['id']}/notes", json={"kind": "note", "text": "x"}, headers=alice)
    assert (await client.delete(f"/api/investigations/{i['id']}", headers=alice)).status_code == 204
    assert (await client.get(f"/api/investigations/{i['id']}", headers=alice)).status_code == 404
    assert (await client.get("/api/investigations", headers=alice)).json() == []
