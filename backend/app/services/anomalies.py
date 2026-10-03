"""Run all detectors for one experiment and store results as POTENTIAL anomalies (never as 'model failure')."""
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomaly.paired import find_discordant
from app.anomaly.statistical import iqr_outliers, isolation_forest_outliers, zscore_outliers
from app.models import Experiment, FailureMode
from app.models.enums import AnomalyStatus
from app.services.metrics import load_rows

PAIRED_LABEL = "representation_sensitivity"
STAT_LABEL = "statistical_outlier"


async def detect_and_store(session: AsyncSession, experiment_id: uuid.UUID) -> list[FailureMode]:
    exp = await session.get(Experiment, experiment_id)
    if exp is None:
        raise ValueError("experiment not found")
    rows = await load_rows(session, experiment_id, exp.task_type)
    run_ids = [r.run_id for r in rows]

    # Keep follow-up verdicts: only replace detections for this experiment's runs, and remember reproduced/not status.
    own = FailureMode.label.in_([PAIRED_LABEL, STAT_LABEL])  # clustering rows live alongside and are left alone
    old = list((await session.execute(select(FailureMode).where(FailureMode.run_id.in_(run_ids), own))).scalars()) if run_ids else []
    previous = {(f.run_id, f.label, f.detector): (f.status, f.details.get("followup_evidence")) for f in old}
    if old:
        await session.execute(delete(FailureMode).where(FailureMode.id.in_([f.id for f in old])))

    found: list[FailureMode] = []

    def add(run_id, label, detector, score, details):  # type: ignore[no-untyped-def]
        status, ev = previous.get((run_id, label, detector), (AnomalyStatus.POTENTIAL_ANOMALY.value, None))
        det = {**details, **({"followup_evidence": ev} if ev else {})}
        fm = FailureMode(run_id=run_id, label=label, detector=detector, status=status, score=score, details=det)
        session.add(fm)
        found.append(fm)

    # 1. Paired discordance (needs problems asked in several forms)
    by_id = {r.run_id: r for r in rows}
    for d in find_discordant([(r.block, r.group, r.passed, r.run_id) for r in rows if r.block and r.group]):
        r = by_id[d.run_id]  # type: ignore[index]
        params = r.variant_params or {}
        add(d.run_id, PAIRED_LABEL, "paired_discordance", None, {
            "block": d.block, "failed_group": d.failed_group, "passing_groups": list(d.passing_groups),
            "failing_groups": list(d.failing_groups), "pair": params.get("pair"),
        })

    # 2. Statistical outliers on numeric features; consensus = how many methods agree on a run
    if len(rows) >= 8:
        feats = {"latency_ms": [r.latency_ms or 0.0 for r in rows], "response_chars": [float(r.response_chars) for r in rows]}
        flags: dict[int, dict[str, list[str]]] = {}
        for name, vals in feats.items():
            for det, idxs in (("iqr", iqr_outliers(vals, k=3.0)), ("zscore", zscore_outliers(vals))):
                for i in idxs:
                    flags.setdefault(i, {}).setdefault(det, []).append(name)
        matrix = [[feats["latency_ms"][i], feats["response_chars"][i]] for i in range(len(rows))]
        for i in isolation_forest_outliers(matrix):
            flags.setdefault(i, {}).setdefault("isolation_forest", []).extend(["latency_ms", "response_chars"])
        for i, by_det in flags.items():
            for det, names in by_det.items():
                add(rows[i].run_id, STAT_LABEL, det, None, {
                    "features": sorted(set(names)), "methods_agreeing": sorted(by_det), "n_methods": len(by_det),
                    "note": "Unusual value among this experiment's runs; not evidence of a model failure."})
    await session.commit()
    return found
