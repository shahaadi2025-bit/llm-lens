"""JSON and CSV exports. CSV cells that start with a formula character are neutralised: model output is untrusted
and spreadsheets execute formulas."""
import csv
import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_VERSION
from app.models import Evaluation, Experiment, ExperimentRun, FailureMode, LLMModel, Metric, ModelVersion, Prompt, Response

_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA):
        return "'" + value
    return value


def to_csv(headers: list[str], rows: list[list[Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(headers)
    for r in rows:
        w.writerow([csv_safe(c) for c in r])
    return buf.getvalue()


def safe_filename(name: str, ext: str) -> str:
    return (re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "export")[:80] + "." + ext


async def _run_rows(session: AsyncSession, exp_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (select(ExperimentRun, Prompt, Response, Evaluation).join(Prompt, Prompt.run_id == ExperimentRun.id)
         .outerjoin(Response, Response.run_id == ExperimentRun.id).outerjoin(Evaluation, Evaluation.run_id == ExperimentRun.id)
         .where(ExperimentRun.experiment_id == exp_id).order_by(ExperimentRun.run_index))
    out = []
    for run, pr, resp, ev in (await session.execute(q)).all():
        out.append({
            "run_index": run.run_index, "variant_label": run.variant_label, "status": run.status, "attempt": run.attempt,
            "seed": run.seed, "latency_ms": run.latency_ms, "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens, "tokens_estimated": bool(resp and resp.raw.get("tokens_estimated")),
            "prompt": pr.text, "expected_answer": pr.expected_answer, "variant_params": pr.variant_params,
            "response": resp.text if resp else None, "passed": ev.passed if ev else None, "score": ev.score if ev else None,
            "evaluator": ev.evaluator_name if ev else None, "evaluator_version": ev.evaluator_version if ev else None,
            "evaluator_kind": ev.kind if ev else None, "error": run.error})
    return out


RUN_COLUMNS = ["run_index", "variant_label", "status", "attempt", "seed", "latency_ms", "prompt_tokens", "completion_tokens",
               "tokens_estimated", "prompt", "expected_answer", "response", "passed", "score", "evaluator", "evaluator_version",
               "evaluator_kind", "error"]


async def runs_csv(session: AsyncSession, exp: Experiment) -> str:
    rows = await _run_rows(session, exp.id)
    return to_csv(RUN_COLUMNS, [[r[c] for c in RUN_COLUMNS] for r in rows])


async def experiment_bundle(session: AsyncSession, exp: Experiment) -> dict[str, Any]:
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    metrics = (await session.execute(select(Metric).where(Metric.experiment_id == exp.id).order_by(Metric.name))).scalars()
    flagged = (await session.execute(select(FailureMode, ExperimentRun.run_index).join(
        ExperimentRun, ExperimentRun.id == FailureMode.run_id).where(ExperimentRun.experiment_id == exp.id))).all()
    return {
        "export": {"generated_at": datetime.now(UTC).isoformat(), "software_version": APP_VERSION,
                   "contains_demo_data": exp.is_demo_data,
                   "notice": "DEMO / MOCK DATA: not real LLM evidence." if exp.is_demo_data else None},
        "experiment": {
            "id": str(exp.id), "name": exp.name, "research_question": exp.research_question, "hypothesis": exp.hypothesis,
            "task_type": exp.task_type, "status": exp.status, "model": model.slug if model else None,
            "model_version": mv.version_label if mv else None, "model_revision": mv.revision if mv else None,
            "temperature": exp.temperature, "max_tokens": exp.max_tokens, "seed": exp.seed, "repetitions": exp.repetitions,
            "evaluator": exp.evaluator, "dataset": exp.dataset_name, "dataset_version": exp.dataset_version, "config": exp.config,
            "spec_hash": exp.spec_hash, "software_version": exp.software_version, "environment": exp.environment,
            "created_at": exp.created_at.isoformat(), "started_at": exp.started_at.isoformat() if exp.started_at else None,
            "finished_at": exp.finished_at.isoformat() if exp.finished_at else None},
        "metrics": [{"name": m.name, "dimension": m.dimension, "value": m.value, "ci_low": m.ci_low, "ci_high": m.ci_high,
                     "ci_level": m.ci_level, "n": m.n, "method": m.method} for m in metrics],
        "runs": await _run_rows(session, exp.id),
        "flagged": [{"run_index": idx, "label": f.label, "detector": f.detector, "status": f.status, "details": f.details}
                    for f, idx in flagged if f.label != "incorrect_answer"],
    }


async def summary_csv(session: AsyncSession, exps: list[Experiment]) -> str:
    """Batch-loaded: a fixed number of queries however many experiments are exported."""
    from sqlalchemy import func

    ids = [e.id for e in exps]
    versions = {mv.id: mv for mv in (await session.execute(select(ModelVersion).where(
        ModelVersion.id.in_({e.model_version_id for e in exps})))).scalars()} if exps else {}
    models = {m.id: m for m in (await session.execute(select(LLMModel).where(
        LLMModel.id.in_({v.model_id for v in versions.values()})))).scalars()} if versions else {}
    acc = {m.experiment_id: m for m in (await session.execute(select(Metric).where(
        Metric.name == "accuracy", Metric.experiment_id.in_(ids)))).scalars()} if ids else {}
    n_runs = dict((await session.execute(select(ExperimentRun.experiment_id, func.count()).where(
        ExperimentRun.experiment_id.in_(ids)).group_by(ExperimentRun.experiment_id))).all()) if ids else {}
    rows = []
    for e in exps:
        mv = versions.get(e.model_version_id)
        model = models.get(mv.model_id) if mv else None
        a = acc.get(e.id)
        rows.append([str(e.id), e.name, e.status, e.task_type, model.slug if model else "", mv.version_label if mv else "",
                     "yes" if e.is_demo_data else "no", n_runs.get(e.id, 0), a.n if a else 0, a.value if a else "",
                     a.ci_low if a else "", a.ci_high if a else "", e.seed, e.created_at.isoformat()])
    return to_csv(["id", "name", "status", "task_type", "model", "version", "mock_data", "runs", "evaluated_runs", "accuracy",
                   "ci_low_95", "ci_high_95", "seed", "created_at"], rows)
