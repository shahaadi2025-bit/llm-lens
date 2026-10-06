"""Regression guards for query counts: list endpoints must cost a fixed number of SQL statements, not one per row."""
import uuid

from sqlalchemy import event

BODY = {"name": "arith", "task_type": "arithmetic_representation", "config": {"n_random_pairs": 11}, "model_slug": "mock-deterministic-v2"}


class Counter:
    def __init__(self, engine):
        self.n = 0
        self._engine = engine.sync_engine
        event.listen(self._engine, "before_cursor_execute", self._hit)

    def _hit(self, *_args):
        self.n += 1

    def reset(self) -> int:
        n, self.n = self.n, 0
        return n


async def make(client, seed):
    r = await client.post("/api/experiments", json={**BODY, "seed": seed})
    await client.post(f"/api/experiments/{r.json()['id']}/run")
    await client.app_engine.wait(uuid.UUID(r.json()["id"]))
    return r.json()


async def test_failure_listing_uses_a_constant_number_of_queries(client, engine):
    counter = Counter(engine)
    await make(client, 1)
    counter.reset()
    few = (await client.get("/api/failures", params={"limit": 3})).json()
    q_few = counter.reset()
    many = (await client.get("/api/failures", params={"limit": 100})).json()
    q_many = counter.reset()
    assert len(few) == 3 and len(many) > 10
    assert q_few == q_many <= 8, (q_few, q_many)  # not 4 per row


async def test_experiment_list_and_exports_do_not_scale_with_row_count(client, engine):
    counter = Counter(engine)
    await make(client, 1)
    counter.reset()
    await client.get("/api/experiments")
    await client.get("/api/exports/experiments.csv")
    one = counter.reset()
    for seed in (2, 3, 4, 5):
        await make(client, seed)
    counter.reset()
    listed = (await client.get("/api/experiments")).json()
    await client.get("/api/exports/experiments.csv")
    five = counter.reset()
    assert len(listed) == 5 and five == one, (one, five)


async def test_cluster_member_listing_is_batched(client, engine):
    counter = Counter(engine)
    await make(client, 1)
    cs = (await client.post("/api/failure-clusters/recompute")).json()
    counter.reset()
    detail = (await client.get(f"/api/failure-clusters/{cs[0]['id']}")).json()
    assert len(detail["members"]) == detail["size"] and detail["size"] >= 3
    assert counter.reset() <= 14  # a handful of queries, independent of cluster size
