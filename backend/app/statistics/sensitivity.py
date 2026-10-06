"""Analysis of one experiment where the same problems are asked in several forms (variants)."""
import re
from dataclasses import dataclass, field

from app.statistics.effect_sizes import cohens_h
from app.statistics.paired_tests import cochran_q
from app.statistics.proportions import Interval, wilson_interval

MIN_BLOCKS_FOR_INFERENCE = 10


def _natural(text: str) -> list[object]:
    """Sort 'pos=10%' before 'pos=100%' (numbers compared as numbers), so position/length charts read left to right."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text)]


@dataclass
class Statement:
    text: str
    evidence_level: str  # observation | correlation | hypothesis | supported_conclusion


@dataclass
class SensitivityAnalysis:
    groups: dict[str, Interval]
    n_blocks: int
    cochran_q: float | None
    cochran_df: int | None
    cochran_p: float | None
    best: str | None
    worst: str | None
    spread: float | None  # best accuracy minus worst accuracy
    cohens_h: float | None
    statements: list[Statement] = field(default_factory=list)


def analyse(rows: list[tuple[str, str, bool]], level: float = 0.95) -> SensitivityAnalysis:
    """rows: (group, block, passed). Groups = forms/variants; blocks = the underlying problem instance."""
    by_group: dict[str, list[bool]] = {}
    cells: dict[str, dict[str, bool]] = {}
    for group, block, passed in rows:
        by_group.setdefault(group, []).append(passed)
        cells.setdefault(block, {})[group] = passed
    groups = {g: wilson_interval(sum(v), len(v), level) for g, v in sorted(by_group.items(), key=lambda kv: _natural(kv[0]))}
    names = list(groups)
    complete = [b for b in cells.values() if all(g in b for g in names)]

    q = df = p = None
    if len(names) >= 2 and complete:
        res = cochran_q([[b[g] for g in names] for b in complete])
        q, df, p = res.statistic, res.df, res.p_value
    best = max(names, key=lambda g: groups[g].estimate) if names else None
    worst = min(names, key=lambda g: groups[g].estimate) if names else None
    spread = groups[best].estimate - groups[worst].estimate if best and worst else None
    h = cohens_h(groups[best].estimate, groups[worst].estimate) if best and worst else None
    out = SensitivityAnalysis(groups, len(complete), q, df, p, best, worst, spread, h)

    if best is None or worst is None:
        return out
    n_total = sum(i.n for i in groups.values())
    out.statements.append(Statement(
        f"Accuracy ranged from {groups[worst].estimate:.0%} ({worst}) to {groups[best].estimate:.0%} ({best}) "
        f"across {len(names)} forms, {n_total} runs in total.", "observation"))
    if len(complete) < MIN_BLOCKS_FOR_INFERENCE:
        out.statements.append(Statement(
            f"Only {len(complete)} complete problem sets: too few to say whether form differences are more than "
            f"chance. Add problems before interpreting differences.", "observation"))
    elif p is None:
        out.statements.append(Statement(
            "Every problem was answered the same way in all forms, so there is no variation to test.", "observation"))
    elif p < 0.05:
        out.statements.append(Statement(
            f"Success rates differ between forms by more than chance variation would readily produce in this sample "
            f"(Cochran's Q = {q:.2f}, df = {df}, p = {p:.3g}, {len(complete)} problems; exploratory, not corrected for "
            f"other analyses). This describes this model on these prompts. It does not identify why.", "correlation"))
    else:
        out.statements.append(Statement(
            f"No reliable difference between forms was detected (Cochran's Q = {q:.2f}, df = {df}, p = {p:.3g}, "
            f"{len(complete)} problems). This is not evidence that no difference exists.", "observation"))
    return out
