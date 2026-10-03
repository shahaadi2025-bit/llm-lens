"""Experiment execution: bounded concurrency, per-run timeout + retry, cancellation, resume, partial results.

Lifecycle: PENDING -> RUNNING -> COMPLETED | FAILED | CANCELLED. FAILED/CANCELLED experiments keep every run
that did finish, and can be started again: only runs that have not succeeded are re-executed (resume).
"""
import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evaluators.base import Evaluator
from app.evaluators.registry import get_evaluator
from app.models import Evaluation, Experiment, ExperimentRun, LLMModel, ModelVersion, Prompt, Response
from app.models.base import utcnow
from app.models.enums import ExperimentStatus, RunStatus
from app.services.adapters.base import GenerationRequest, ModelAdapter
from app.services.anomalies import detect_and_store
from app.services.followup_evidence import update_parent_failures
from app.services.metrics import compute_and_store_metrics

log = logging.getLogger(__name__)
AdapterProvider = Callable[[str], ModelAdapter]  # model slug -> adapter; raises ModelUnavailable


class EngineError(Exception):
    status_code = 409


class ModelUnavailable(EngineError):
    pass


@dataclass
class _Prepared:
    experiment_id: uuid.UUID
    adapter: ModelAdapter
    evaluator: Evaluator
    temperature: float
    max_tokens: int
    run_ids: list[uuid.UUID]


class ExperimentEngine:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], adapter_provider: AdapterProvider, *,
                 max_concurrency: int = 4, run_timeout_s: float = 60.0, max_retries: int = 2,
                 retry_backoff_s: float = 0.5) -> None:
        self._sm = sessionmaker
        self._adapter_provider = adapter_provider
        self._max_concurrency = max_concurrency
        self._timeout = run_timeout_s
        self._max_retries = max_retries
        self._backoff = retry_backoff_s
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}

    # ---- public API -------------------------------------------------------------------------------------------
    async def start(self, experiment_id: uuid.UUID) -> None:
        """Transition to RUNNING synchronously, then execute in the background."""
        prepared = await self.prepare(experiment_id)
        task = asyncio.create_task(self._execute(prepared))
        self._tasks[experiment_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(experiment_id, None))

    async def execute(self, experiment_id: uuid.UUID) -> None:
        """Run to completion in the caller's task (used by the CLI and tests)."""
        await self._execute(await self.prepare(experiment_id))

    def cancel(self, experiment_id: uuid.UUID) -> bool:
        task = self._tasks.get(experiment_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def wait(self, experiment_id: uuid.UUID) -> None:
        task = self._tasks.get(experiment_id)
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def is_active(self, experiment_id: uuid.UUID) -> bool:
        task = self._tasks.get(experiment_id)
        return task is not None and not task.done()

    # ---- internals --------------------------------------------------------------------------------------------
    async def prepare(self, experiment_id: uuid.UUID) -> _Prepared:
        async with self._sm() as s:
            exp = await s.get(Experiment, experiment_id)
            if exp is None:
                raise EngineError(f"experiment {experiment_id} not found")
            if exp.status == ExperimentStatus.RUNNING.value and self.is_active(experiment_id):
                raise EngineError("experiment is already running")
            mv = await s.get(ModelVersion, exp.model_version_id)
            model = await s.get(LLMModel, mv.model_id) if mv else None
            if model is None:
                raise EngineError("experiment references an unknown model")
            adapter = self._adapter_provider(model.slug)  # may raise ModelUnavailable
            evaluator = get_evaluator(exp.evaluator)

            # Resume: anything that has not succeeded is reset and re-run.
            await s.execute(update(ExperimentRun).where(
                ExperimentRun.experiment_id == experiment_id,
                ExperimentRun.status.in_([RunStatus.FAILED.value, RunStatus.CANCELLED.value, RunStatus.RUNNING.value]),
            ).values(status=RunStatus.PENDING.value, error=None))
            exp.status = ExperimentStatus.RUNNING.value
            exp.started_at = exp.started_at or utcnow()
            exp.finished_at = None
            exp.error = None
            run_ids = list((await s.execute(select(ExperimentRun.id).where(
                ExperimentRun.experiment_id == experiment_id, ExperimentRun.status == RunStatus.PENDING.value,
            ).order_by(ExperimentRun.run_index))).scalars())
            await s.commit()
            return _Prepared(experiment_id, adapter, evaluator, exp.temperature, exp.max_tokens, run_ids)

    async def _execute(self, p: _Prepared) -> None:
        sem = asyncio.Semaphore(self._max_concurrency)
        try:
            await asyncio.gather(*(self._run_one(rid, p, sem) for rid in p.run_ids))
        except asyncio.CancelledError:
            await self._finalize(p.experiment_id, cancelled=True)
            raise
        await self._finalize(p.experiment_id)

    async def _run_one(self, run_id: uuid.UUID, p: _Prepared, sem: asyncio.Semaphore) -> None:
        async with sem, self._sm() as s:
            run = await s.get(ExperimentRun, run_id)
            prompt = (await s.execute(select(Prompt).where(Prompt.run_id == run_id))).scalar_one()
            assert run is not None
            run.status = RunStatus.RUNNING.value
            run.started_at = utcnow()
            await s.commit()

            result = None
            error: str | None = None
            for attempt in range(1, self._max_retries + 2):
                run.attempt = attempt
                try:
                    result = await asyncio.wait_for(p.adapter.generate(GenerationRequest(
                        prompt=prompt.text, system=prompt.system_text, temperature=p.temperature,
                        max_tokens=p.max_tokens, seed=run.seed)), timeout=self._timeout)
                    error = None
                    break
                except TimeoutError:
                    error = f"timeout after {self._timeout}s"
                except Exception as exc:  # noqa: BLE001 - any provider failure is a retryable run error
                    error = f"{type(exc).__name__}: {exc}"
                if attempt <= self._max_retries:
                    await asyncio.sleep(self._backoff * attempt)

            run.finished_at = utcnow()
            if result is None:
                run.status, run.error = RunStatus.FAILED.value, error
                await s.commit()
                return

            text = result.text or ""
            estimated = result.prompt_tokens is None or result.completion_tokens is None
            run.latency_ms = (run.finished_at - run.started_at).total_seconds() * 1000
            run.prompt_tokens = result.prompt_tokens if result.prompt_tokens is not None else \
                p.adapter.estimate_tokens(prompt.text)
            run.completion_tokens = result.completion_tokens if result.completion_tokens is not None else \
                p.adapter.estimate_tokens(text)
            raw: dict[str, Any] = {**result.raw, "tokens_estimated": estimated}
            s.add(Response(run_id=run_id, text=text, finish_reason=result.finish_reason,
                           is_empty=not text.strip(), raw=raw))
            try:
                ev = p.evaluator.evaluate(text, prompt.expected_answer)
            except Exception as exc:  # noqa: BLE001
                run.status, run.error = RunStatus.FAILED.value, f"evaluator error: {type(exc).__name__}: {exc}"
                await s.commit()
                return
            s.add(Evaluation(run_id=run_id, kind=p.evaluator.kind, evaluator_name=p.evaluator.name,
                             evaluator_version=p.evaluator.version, score=ev.score, passed=ev.passed,
                             details=ev.details))
            run.status = RunStatus.SUCCEEDED.value
            await s.commit()

    async def _finalize(self, experiment_id: uuid.UUID, *, cancelled: bool = False) -> None:
        async with self._sm() as s:
            exp = await s.get(Experiment, experiment_id)
            assert exp is not None
            statuses = list((await s.execute(select(ExperimentRun.status).where(
                ExperimentRun.experiment_id == experiment_id))).scalars())
            if cancelled:
                await s.execute(update(ExperimentRun).where(
                    ExperimentRun.experiment_id == experiment_id,
                    ExperimentRun.status.in_([RunStatus.PENDING.value, RunStatus.RUNNING.value]),
                ).values(status=RunStatus.CANCELLED.value))
                exp.status = ExperimentStatus.CANCELLED.value
            else:
                unfinished = sum(1 for x in statuses if x != RunStatus.SUCCEEDED.value)
                if unfinished:
                    exp.status = ExperimentStatus.FAILED.value
                    exp.error = (f"{unfinished} of {len(statuses)} runs did not succeed; partial results are kept "
                                 "and the experiment can be resumed.")
                else:
                    exp.status = ExperimentStatus.COMPLETED.value
            exp.finished_at = utcnow()
            await s.commit()
        try:  # analysis must never turn a finished experiment into a failed one
            async with self._sm() as s:
                await compute_and_store_metrics(s, experiment_id)
                await detect_and_store(s, experiment_id)
                if not cancelled:
                    await update_parent_failures(s, experiment_id)
        except Exception:  # noqa: BLE001
            log.exception("analysis failed for %s", experiment_id)
