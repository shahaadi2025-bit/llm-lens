import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.experiments.engine import ExperimentEngine, ModelUnavailable
from app.experiments.service import (
    DuplicateExperiment,
    ServiceError,
    TooLarge,
    clone_experiment,
    create_experiment,
    ensure_model_version,
)
from app.models import Evaluation, Experiment, ExperimentLineage, ExperimentRun, Response
from app.schemas.experiment import ExperimentCreate
from app.services.adapters.base import AdapterError, GenerationRequest, GenerationResult
from app.services.adapters.mock import MockAdapter

SETTINGS = Settings(model_provider="mock")
SPEC = ExperimentCreate(name="t", task_type="arithmetic_representation", config={"pairs": [[37, 84]]})  # 6 runs


class Scripted(MockAdapter):
    """Mock with injectable misbehaviour."""

    def __init__(self, fail_first: int = 0, always_fail: bool = False, delay: float = 0.0, empty: bool = False):
        super().__init__()
        self.calls = 0
        self.fail_first, self.always_fail, self.delay, self.empty = fail_first, always_fail, delay, empty

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.always_fail or self.calls <= self.fail_first:
            raise AdapterError("boom")
        if self.empty:
            return GenerationResult(text="", finish_reason="stop")
        return await super().generate(request)


async def make(engine, adapter, spec=SPEC, **kw):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        info = adapter.get_model_info()
        mv = await ensure_model_version(s, info)
        exp = await create_experiment(s, spec, mv, info, SETTINGS)
    eng = ExperimentEngine(sm, lambda slug: adapter, retry_backoff_s=0.0, **kw)
    return sm, eng, exp.id


async def runs(sm, exp_id):
    async with sm() as s:
        return list((await s.execute(select(ExperimentRun).where(ExperimentRun.experiment_id == exp_id)
                                     .order_by(ExperimentRun.run_index))).scalars())


async def status(sm, exp_id):
    async with sm() as s:
        return (await s.get(Experiment, exp_id)).status


async def test_successful_run_persists_everything(engine):
    sm, eng, eid = await make(engine, MockAdapter())
    await eng.execute(eid)
    assert await status(sm, eid) == "completed"
    rs = await runs(sm, eid)
    assert len(rs) == 6 and all(r.status == "succeeded" and r.latency_ms is not None for r in rs)
    async with sm() as s:
        assert (await s.execute(select(func.count()).select_from(Response))).scalar_one() == 6
        evs = list((await s.execute(select(Evaluation))).scalars())
        assert len(evs) == 6 and all(e.kind == "deterministic" and e.evaluator_name == "numeric_match" for e in evs)
        exp = await s.get(Experiment, eid)
        assert exp.is_demo_data and exp.software_version and exp.environment["python"]


async def test_retry_recovers_from_transient_failures(engine):
    adapter = Scripted(fail_first=2)
    sm, eng, eid = await make(engine, adapter, max_concurrency=1, max_retries=2)
    await eng.execute(eid)
    assert await status(sm, eid) == "completed"
    assert (await runs(sm, eid))[0].attempt == 3


async def test_persistent_failure_marks_failed_and_resume_finishes(engine):
    adapter = Scripted(always_fail=True)
    sm, eng, eid = await make(engine, adapter, max_retries=1)
    await eng.execute(eid)
    assert await status(sm, eid) == "failed"
    rs = await runs(sm, eid)
    assert all(r.status == "failed" and "boom" in r.error and r.attempt == 2 for r in rs)
    adapter.always_fail = False  # provider recovers -> resume
    await eng.execute(eid)
    assert await status(sm, eid) == "completed"


async def test_partial_results_kept_and_only_unfinished_rerun(engine):
    adapter = Scripted(fail_first=3)  # first run (1 try + 0 retries each) and next two fail, rest succeed
    sm, eng, eid = await make(engine, adapter, max_concurrency=1, max_retries=0)
    await eng.execute(eid)
    assert await status(sm, eid) == "failed"
    done_before = [r.id for r in await runs(sm, eid) if r.status == "succeeded"]
    assert len(done_before) == 3
    calls_before = adapter.calls
    await eng.execute(eid)
    assert adapter.calls - calls_before == 3  # resumed only the 3 failed runs
    assert await status(sm, eid) == "completed"


async def test_timeout_is_a_failure_not_a_hang(engine):
    sm, eng, eid = await make(engine, Scripted(delay=1.0), run_timeout_s=0.05, max_retries=0)
    await asyncio.wait_for(eng.execute(eid), timeout=5)
    rs = await runs(sm, eid)
    assert await status(sm, eid) == "failed" and all("timeout" in r.error for r in rs)


async def test_empty_response_is_stored_and_scored_zero(engine):
    sm, eng, eid = await make(engine, Scripted(empty=True))
    await eng.execute(eid)
    async with sm() as s:
        resp = list((await s.execute(select(Response))).scalars())
        assert all(r.is_empty for r in resp)
        evs = list((await s.execute(select(Evaluation))).scalars())
        assert all(e.score == 0.0 and e.details["reason"] == "empty_response" for e in evs)


async def test_cancellation_then_resume(engine):
    adapter = Scripted(delay=0.2)
    sm, eng, eid = await make(engine, adapter, max_concurrency=1)
    await eng.start(eid)
    await asyncio.sleep(0.5)  # a couple of runs finish
    assert eng.cancel(eid)
    await eng.wait(eid)
    assert await status(sm, eid) == "cancelled"
    statuses = {r.status for r in await runs(sm, eid)}
    assert "succeeded" in statuses and "cancelled" in statuses and "running" not in statuses
    adapter.delay = 0
    await eng.execute(eid)
    assert await status(sm, eid) == "completed"


async def test_concurrency_limit_respected(engine):
    class Probe(MockAdapter):
        active = peak = 0

        async def generate(self, request):
            Probe.active += 1
            Probe.peak = max(Probe.peak, Probe.active)
            await asyncio.sleep(0.02)
            Probe.active -= 1
            return await super().generate(request)

    sm, eng, eid = await make(engine, Probe(), max_concurrency=2)
    await eng.execute(eid)
    assert Probe.peak == 2


async def test_cannot_start_twice_and_unknown_model(engine):
    sm, eng, eid = await make(engine, Scripted(delay=0.2))
    await eng.start(eid)
    with pytest.raises(Exception, match="already running"):
        await eng.start(eid)
    await eng.wait(eid)

    def refuse(slug):
        raise ModelUnavailable("nope")

    eng2 = ExperimentEngine(sm, refuse)
    with pytest.raises(ModelUnavailable):
        await eng2.prepare(eid)


async def test_duplicate_detection_and_clone_lineage(engine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    info = MockAdapter().get_model_info()
    async with sm() as s:
        mv = await ensure_model_version(s, info)
        exp = await create_experiment(s, SPEC, mv, info, SETTINGS)
        with pytest.raises(DuplicateExperiment) as e:
            await create_experiment(s, SPEC, mv, info, SETTINGS)
        assert e.value.existing_id == exp.id
        clone = await clone_experiment(s, exp, info, SETTINGS, mv)
        assert clone.id != exp.id and clone.name.endswith("(clone)")
        edge = (await s.execute(select(ExperimentLineage))).scalar_one()
        assert (edge.parent_experiment_id, edge.child_experiment_id, edge.relation) == (exp.id, clone.id, "clone")
        # same seed + config -> same prompts: the clone is reproducible
        assert exp.spec_hash == clone.spec_hash


async def test_size_limit_and_invalid_type(engine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    info = MockAdapter().get_model_info()
    tiny = Settings(model_provider="mock", max_runs_per_experiment=5)
    async with sm() as s:
        mv = await ensure_model_version(s, info)
        with pytest.raises(TooLarge):
            await create_experiment(s, SPEC, mv, info, tiny)
        with pytest.raises(ServiceError):
            await create_experiment(s, ExperimentCreate(name="x", task_type="nope"), mv, info, SETTINGS)
        with pytest.raises(ServiceError):
            await create_experiment(s, ExperimentCreate(name="x", task_type="arithmetic_representation",
                                                        config={"pairs": [[1, 1]]}), mv, info, SETTINGS)
