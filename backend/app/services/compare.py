"""Compare two model versions on MATCHED experiments only (identical task, config, seed, settings and evaluator),
so any difference is not an artefact of different problems. Never attributes a cause to the difference."""
import hashlib
import json
import uuid
from collections import defaultdict

from scipy import stats
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Experiment, LLMModel, Metric, ModelVersion, User
from app.models.enums import ExperimentStatus
from app.schemas.fingerprint import CompareOut, DiffOut, ExperimentRef, MatchedDesign
from app.services.access import visible
from app.services.metrics import load_rows
from app.statistics.effect_sizes import cohens_h
from app.statistics.proportions import newcombe_difference


def design_hash(e: Experiment) -> str:
    """Everything that defines the questions asked, excluding which model answered."""
    return hashlib.sha256(json.dumps({
        "t": e.task_type, "c": e.config, "s": e.seed, "temp": e.temperature, "mt": e.max_tokens,
        "r": e.repetitions, "ev": e.evaluator}, sort_keys=True, default=str).encode()).hexdigest()


async def _completed(session: AsyncSession, version_id: uuid.UUID, user: User | None) -> dict[str, Experiment]:
    exps = (await session.execute(select(Experiment).where(
        visible(user), Experiment.model_version_id == version_id, Experiment.status == ExperimentStatus.COMPLETED.value)
        .order_by(Experiment.created_at.desc()))).scalars()
    out: dict[str, Experiment] = {}
    for e in exps:
        out.setdefault(design_hash(e), e)  # newest completed experiment per design
    return out


async def _metric(session: AsyncSession, exp_id: uuid.UUID, name: str) -> Metric | None:
    return (await session.execute(select(Metric).where(Metric.experiment_id == exp_id, Metric.name == name))).scalar_one_or_none()


def _statement(label: str, d: float, lo: float, hi: float, demo: bool) -> str:
    pts = abs(d) * 100
    if lo <= 0 <= hi:
        s = (f"{label}: the difference ({d * 100:+.1f} percentage points, 95% CI [{lo * 100:+.1f}, {hi * 100:+.1f}]) is "
             f"compatible with no difference. This is not evidence that the versions behave the same.")
    else:
        s = (f"{label}: version B scored {pts:.1f} percentage points {'higher' if d > 0 else 'lower'} (95% CI "
             f"[{lo * 100:+.1f}, {hi * 100:+.1f}]). This describes outcomes on these experiments; it does not say what "
             f"changed between the versions.")
    return s + (" (DEMO: the mock versions differ by an injected error rate, by construction.)" if demo else "")


async def compare_versions(session: AsyncSession, a_id: uuid.UUID, b_id: uuid.UUID, user: User | None = None) -> CompareOut:
    a_mv, b_mv = await session.get(ModelVersion, a_id), await session.get(ModelVersion, b_id)
    if a_mv is None or b_mv is None:
        raise ValueError("unknown model version")
    a_model, b_model = await session.get(LLMModel, a_mv.model_id), await session.get(LLMModel, b_mv.model_id)
    assert a_model and b_model
    demo = a_model.is_mock or b_model.is_mock
    A, B = await _completed(session, a_id, user), await _completed(session, b_id, user)
    shared = sorted(set(A) & set(B))

    pooled: dict[tuple[str, str | None], list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # kA nA kB nB
    paired_only: dict[str | None, list[int]] = defaultdict(lambda: [0, 0])  # per dimension: only A correct, only B correct
    lat: dict[str, list[tuple[float, int]]] = {"a": [], "b": []}
    matched = []
    for h in shared:
        ea, eb = A[h], B[h]
        matched.append(MatchedDesign(task_type=ea.task_type, a=ExperimentRef(id=ea.id, name=ea.name),
                                     b=ExperimentRef(id=eb.id, name=eb.name)))
        dim: str | None = None
        for name in ("accuracy", "empty_response_rate"):
            ma, mb = await _metric(session, ea.id, name), await _metric(session, eb.id, name)
            if ma is None or mb is None:
                continue
            if name == "accuracy":
                dim = ma.dimension
            p = pooled[(name, ma.dimension)]
            p[0] += round(ma.value * ma.n)
            p[1] += ma.n
            p[2] += round(mb.value * mb.n)
            p[3] += mb.n
        for side, e in (("a", ea), ("b", eb)):
            m = await _metric(session, e.id, "latency_ms_mean")
            if m:
                lat[side].append((m.value, m.n))
        # Identical design and seed means identical prompts, run for run: usable for a paired comparison.
        ra, rb = await load_rows(session, ea.id, ea.task_type), await load_rows(session, eb.id, eb.task_type)
        if ra and len(ra) == len(rb):
            paired_only[dim][0] += sum(1 for x, y in zip(ra, rb, strict=True) if x.passed and not y.passed)
            paired_only[dim][1] += sum(1 for x, y in zip(ra, rb, strict=True) if y.passed and not x.passed)

    diffs = []
    for (name, dim), (ka, na, kb, nb) in sorted(pooled.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if na == 0 or nb == 0:
            continue
        d, lo, hi = newcombe_difference(ka, na, kb, nb)
        pa, pb = ka / na, kb / nb
        label = f"{name} ({dim})" if dim else name
        oa = ob = mp = None
        if name == "accuracy" and dim in paired_only:
            oa, ob = paired_only[dim]
            if oa + ob > 0:
                mp = float(stats.binomtest(min(oa, ob), oa + ob, 0.5).pvalue)  # exact McNemar
        diffs.append(DiffOut(
            metric=name, dimension=dim, a_value=pa, a_n=na, b_value=pb, b_n=nb, difference=d, diff_ci_low=lo, diff_ci_high=hi,
            cohens_h=cohens_h(pb, pa), mcnemar_p=mp, paired_only_a=oa, paired_only_b=ob,
            statement=_statement(label, d, lo, hi, demo)))
    lat_out = {s: (sum(v * n for v, n in xs) / sum(n for _, n in xs) if xs else None) for s, xs in lat.items()}
    notes = ["Only experiments with identical design (task, config, seed, settings, evaluator) are compared.",
             "Intervals: Newcombe hybrid-score 95% CI for the difference. McNemar (exact) is exploratory and uses the identical prompts.",
             "Latency is a descriptive n-weighted mean without an interval; free-tier and mock latencies are not benchmarks."]
    return CompareOut(
        a_label=f"{a_model.slug} {a_mv.version_label}", b_label=f"{b_model.slug} {b_mv.version_label}", includes_demo_data=demo,
        comparable=bool(shared), matched=matched,
        unmatched_a=[ExperimentRef(id=e.id, name=e.name) for h, e in A.items() if h not in B],
        unmatched_b=[ExperimentRef(id=e.id, name=e.name) for h, e in B.items() if h not in A],
        differences=diffs, latency_ms=lat_out, notes=notes)
