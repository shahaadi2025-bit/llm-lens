"""Update the verdict on a flagged anomaly once its controlled follow-up experiment has finished."""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExperimentLineage, FailureMode
from app.models.enums import AnomalyStatus
from app.services.metrics import load_rows
from app.statistics.proportions import wilson_interval

RULE = (
    "Reproduced if the originally failing form fails in at least half of its follow-up runs and its Wilson 95% lower "
    "bound exceeds the failure rate of the other forms. Strength: strong if the lower bound is >= 0.6, moderate if "
    ">= 0.4, otherwise weak."
)
MIN_RUNS = 2


def followup_verdict(k_form: int, n_form: int, k_other: int, n_other: int) -> dict[str, Any]:
    """k_* = failures, n_* = runs. Pure function so the rule is easy to test and audit."""
    p_form = k_form / n_form
    p_other = k_other / n_other if n_other else 0.0
    lb = wilson_interval(k_form, n_form).low
    if p_form >= 0.5 and lb >= 0.6:
        strength = "strong"
    elif p_form >= 0.5 and lb >= 0.4:
        strength = "moderate"
    elif p_form >= 0.5 and lb > p_other:
        strength = "weak"
    else:
        strength = "none"
    reproduced = strength != "none" and lb > p_other
    return {"status": AnomalyStatus.REPRODUCED.value if reproduced else AnomalyStatus.NOT_REPRODUCED.value,
            "strength": strength if reproduced else "none", "form_failures": k_form, "form_runs": n_form,
            "other_failures": k_other, "other_runs": n_other, "wilson_lower_bound": round(lb, 4), "rule": RULE}


async def update_parent_failures(session: AsyncSession, child_id: uuid.UUID) -> int:
    edges = (await session.execute(select(ExperimentLineage).where(
        ExperimentLineage.child_experiment_id == child_id, ExperimentLineage.trigger_run_id.is_not(None)))).scalars()
    from app.models import Experiment  # local import avoids a cycle at module load

    child = await session.get(Experiment, child_id)
    if child is None:
        return 0
    rows = await load_rows(session, child_id, child.task_type)
    updated = 0
    for edge in edges:
        fm = (await session.execute(select(FailureMode).where(
            FailureMode.run_id == edge.trigger_run_id, FailureMode.detector == "paired_discordance"))).scalar_one_or_none()
        if fm is None:
            continue
        form = fm.details.get("failed_group")
        in_form = [r for r in rows if r.group == form]
        other = [r for r in rows if r.group and r.group != form]
        if len(in_form) < MIN_RUNS:
            continue
        verdict = followup_verdict(sum(not r.passed for r in in_form), len(in_form),
                                   sum(not r.passed for r in other), len(other))
        fm.status = verdict.pop("status")
        fm.details = {**fm.details, "followup_evidence": {**verdict, "child_experiment_id": str(child_id)}}
        updated += 1
    await session.commit()
    return updated
