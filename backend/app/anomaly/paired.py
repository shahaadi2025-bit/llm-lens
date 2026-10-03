"""Discordance detector: the same problem answered correctly in some forms and incorrectly in others.

This is the trigger for follow-up experiments. It flags the failing runs as POTENTIAL anomalies only.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Discordance:
    block: str
    failed_group: str
    run_id: object
    passing_groups: tuple[str, ...]
    failing_groups: tuple[str, ...]


def find_discordant(cells: list[tuple[str, str, bool, object]]) -> list[Discordance]:
    """cells: (block, group, passed, run_id). A block is discordant if it has both passes and failures.
    Blocks where every form failed are not flagged here: that is a hard problem, not form sensitivity."""
    blocks: dict[str, list[tuple[str, bool, object]]] = {}
    for block, group, passed, run_id in cells:
        blocks.setdefault(block, []).append((group, passed, run_id))
    out = []
    for block, items in sorted(blocks.items()):
        passing = tuple(sorted(g for g, ok, _ in items if ok))
        failing = tuple(sorted(g for g, ok, _ in items if not ok))
        if passing and failing:
            for g, ok, run_id in items:
                if not ok:
                    out.append(Discordance(block, g, run_id, passing, failing))
    return out
