import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import Metric, MetricEvidence
from app.services.adapters.mock import MockAdapter
from app.services.metrics import compute_and_store_metrics
from tests.test_engine import make


async def test_engine_stores_metrics_with_cis_and_evidence(engine):
    sm, eng, eid = await make(engine, MockAdapter())
    await eng.execute(eid)
    async with sm() as s:
        ms = list((await s.execute(select(Metric).where(Metric.experiment_id == eid))).scalars())
        names = {m.name for m in ms}
        assert "accuracy" in names and "empty_response_rate" in names
        assert sum(n.startswith("accuracy[") for n in names) == 6  # one per representation
        acc = next(m for m in ms if m.name == "accuracy")
        assert acc.dimension == "M" and acc.n == 6 and acc.ci_low <= acc.value <= acc.ci_high
        assert acc.method == "wilson-95" and acc.ci_level == 0.95
        ev = (await s.execute(select(func.count()).select_from(MetricEvidence)
                              .where(MetricEvidence.metric_id == acc.id))).scalar_one()
        assert ev == 6  # every counted run is traceable


async def test_recompute_is_idempotent(engine):
    sm, eng, eid = await make(engine, MockAdapter())
    await eng.execute(eid)
    async with sm() as s:
        before = (await s.execute(select(func.count()).select_from(Metric))).scalar_one()
        await compute_and_store_metrics(s, eid)
        await compute_and_store_metrics(s, eid)
        assert (await s.execute(select(func.count()).select_from(Metric))).scalar_one() == before
        assert (await s.execute(select(func.count()).select_from(MetricEvidence))).scalar_one() > 0


async def test_no_metrics_when_nothing_succeeded(engine):
    from tests.test_engine import Scripted

    sm, eng, eid = await make(engine, Scripted(always_fail=True), max_retries=0)
    await eng.execute(eid)
    async with sm() as s:
        assert (await s.execute(select(func.count()).select_from(Metric))).scalar_one() == 0


async def test_metrics_for_unknown_experiment_raises(engine):
    async with async_sessionmaker(engine)() as s:
        with pytest.raises(ValueError):
            await compute_and_store_metrics(s, uuid.uuid4())


