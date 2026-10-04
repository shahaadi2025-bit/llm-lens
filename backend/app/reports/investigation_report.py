"""Report for a notebook investigation: the researcher's question, hypothesis, linked experiments, notes and conclusion.
The conclusion is the researcher's own words and is printed with the limitations they were required to state."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Experiment, Investigation, InvestigationExperiment, InvestigationNote, Metric, User
from app.reports.markdown_utils import interval, md_text, pct, table
from app.services.access import can_see


async def build_investigation_report(session: AsyncSession, inv: Investigation, user: User) -> tuple[str, str, bool]:
    ids = list((await session.execute(select(InvestigationExperiment.experiment_id).where(
        InvestigationExperiment.investigation_id == inv.id))).scalars())
    exps = [e for e in [await session.get(Experiment, i) for i in ids] if e is not None and can_see(e, user)]
    notes = list((await session.execute(select(InvestigationNote).where(InvestigationNote.investigation_id == inv.id)
                                        .order_by(InvestigationNote.created_at))).scalars())
    demo = any(e.is_demo_data for e in exps)

    L = [f"# Investigation report: {md_text(inv.title, 150)}\n"]
    if demo:
        L.append("> **DEMO / MOCK DATA.** At least one linked experiment ran on a mock model; its results are not evidence "
                 "about any real language model.\n")
    L += ["## Research question\n", (md_text(inv.research_question, 1500) or "*Not stated.*") + "\n",
          "## Hypothesis\n", (md_text(inv.hypothesis, 1500) or "*Not stated.*") + "\n", "## Experiments\n"]
    rows = []
    for e in exps:
        acc = (await session.execute(select(Metric).where(Metric.experiment_id == e.id, Metric.name == "accuracy"))).scalar_one_or_none()
        rows.append([md_text(e.name, 80), e.status, e.task_type, pct(acc.value) if acc else "n/a",
                     interval(acc.ci_low, acc.ci_high) if acc else "n/a", str(acc.n) if acc else "0", "yes" if e.is_demo_data else "no",
                     f"`{e.id}`"])
    L.append(table(["Experiment", "Status", "Type", "Accuracy", "95% interval", "n", "Mock data", "ID"], rows))
    hidden = len(ids) - len(exps)
    if hidden:
        L.append(f"\n*{hidden} linked experiment(s) are not visible to you and are omitted.*\n")
    for kind, title in (("observation", "Observations"), ("hypothesis", "Hypotheses to test"), ("note", "Notes")):
        sel = [n for n in notes if n.kind == kind]
        L.append(f"\n## {title}\n")
        L += [f"- {md_text(n.text, 1000)}" for n in sel] if sel else ["*(none)*"]
    L += ["\n## Conclusion\n", md_text(inv.conclusion, 2000) if inv.conclusion else "No conclusion has been recorded.", "\n## Limitations\n",
          md_text(inv.limitations, 2000) if inv.limitations else "No limitations have been recorded.", "",
          "\n---\n*This report assembles the researcher's notes with stored experiment results. Black-box experiments cannot "
          "establish internal mechanisms; any such claim in the notes is the author's, not the platform's.*\n"]
    return f"Investigation report: {inv.title}", "\n".join(L), demo
