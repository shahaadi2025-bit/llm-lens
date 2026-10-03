"""Build the 'Explain this failure' view: observation -> controls -> change -> follow-ups -> evidence -> explanations.

Everything stated is either an observation, a reproduced pattern (correlation) or a labelled hypothesis. No internal
mechanism is ever asserted: a black-box experiment cannot observe one.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Experiment, ExperimentLineage, ExperimentRun, FailureMode, LLMModel, ModelVersion, Prompt
from app.schemas.failures import EvidenceOut, ExplainOut, ExplainStep, FailureOut, FollowUpSummary

LIMITATIONS = [
    "This is a black-box experiment: it can show that behavior changed with the prompt form, not why inside the model.",
    "A reproduced pattern holds for this model, this problem and these settings; it may not generalize to other problems.",
    "At temperature 0 a deterministic model repeats itself; reproduction then mostly tests the surface forms, not randomness.",
    "The evaluator extracts the last number in the response; check the raw response before trusting the verdict.",
]


async def failure_out(session: AsyncSession, fm: FailureMode) -> FailureOut:
    run = await session.get(ExperimentRun, fm.run_id)
    assert run is not None
    exp = await session.get(Experiment, run.experiment_id)
    assert exp is not None
    prompt = (await session.execute(select(Prompt).where(Prompt.run_id == run.id))).scalar_one()
    from app.models import Response

    resp = (await session.execute(select(Response).where(Response.run_id == run.id))).scalar_one_or_none()
    return FailureOut(
        id=fm.id, run_id=run.id, experiment_id=exp.id, experiment_name=exp.name, label=fm.label, detector=fm.detector,
        status=fm.status, details=fm.details, prompt=prompt.text, response=resp.text if resp else None,
        expected_answer=prompt.expected_answer, is_demo_data=exp.is_demo_data,
        can_follow_up=fm.detector == "paired_discordance")


async def explain(session: AsyncSession, fm: FailureMode) -> ExplainOut:
    fo = await failure_out(session, fm)
    exp = await session.get(Experiment, fo.experiment_id)
    assert exp is not None
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    d = fm.details

    if fm.detector == "paired_discordance":
        pair = d.get("pair") or ["?", "?"]
        observed = (f"For the problem {pair[0]}×{pair[1]}, the form '{d['failed_group']}' was answered "
                    f"{fo.response!r} (expected {fo.expected_answer}), while the form(s) "
                    f"{', '.join(d['passing_groups'])} were answered correctly.")
        changed = "The surface form of the prompt (operand order, operator symbol, wording or a named mutation)."
        controls = [f"model: {model.slug if model else '?'} ({mv.version_label if mv else '?'})",
                    f"temperature {exp.temperature}, max tokens {exp.max_tokens}", f"evaluator: {exp.evaluator}",
                    f"problem held fixed: {pair[0]}×{pair[1]}", f"seed {exp.seed}"]
    else:
        observed = (f"One run had an unusual value for {', '.join(d.get('features', []))} compared with the other runs of this "
                    f"experiment (flagged by {', '.join(d.get('methods_agreeing', [fm.detector]))}).")
        changed = "None identified: this is a statistical outlier, not a controlled comparison."
        controls = [f"model: {model.slug if model else '?'}", f"evaluator: {exp.evaluator}"]

    edges = list((await session.execute(select(ExperimentLineage).where(
        ExperimentLineage.parent_experiment_id == exp.id, ExperimentLineage.trigger_run_id == fm.run_id))).scalars())
    follow = []
    ev = d.get("followup_evidence")
    for e in edges:
        child = await session.get(Experiment, e.child_experiment_id)
        if child is None:
            continue
        summary = None
        if ev and ev.get("child_experiment_id") == str(child.id):
            summary = (f"The failing form failed in {ev['form_failures']}/{ev['form_runs']} follow-up runs; the other forms "
                       f"failed in {ev['other_failures']}/{ev['other_runs']}.")
        follow.append(FollowUpSummary(experiment_id=child.id, name=child.name, status=child.status, summary=summary))

    if ev and fm.status == "reproduced":
        evidence = EvidenceOut(level="correlation", strength=ev["strength"], status=fm.status, summary=(
            f"Reproduced: {ev['form_failures']}/{ev['form_runs']} follow-up runs of the failing form were incorrect versus "
            f"{ev['other_failures']}/{ev['other_runs']} for the other forms. This is a reproduced association between prompt "
            f"form and correctness for this problem, not an identified cause."))
    elif ev:
        evidence = EvidenceOut(level="observation", strength="none", status=fm.status, summary=(
            f"Not reproduced: the failing form was incorrect in {ev['form_failures']}/{ev['form_runs']} follow-up runs. The "
            f"original error is consistent with chance variation, though that is not proven either."))
    else:
        evidence = EvidenceOut(level="observation", strength="none", status=fm.status,
                               summary="A single observation. No completed follow-up experiment yet, so nothing is reproduced.")

    possible, alternatives = [], []
    if fm.detector == "paired_discordance":
        a, b = d.get("pair") or ("?", "?")
        possible.append(ExplainStep(text=f"The model is less reliable on {a}×{b} when asked in form '{d['failed_group']}'.",
                                    evidence_level="hypothesis"))
        alternatives += [
            ExplainStep(text="Sampling variability: one incorrect answer among several forms can occur by chance.",
                        evidence_level="hypothesis"),
            ExplainStep(text="Evaluator artifact: the last-number rule may have misread a correct response. Check the raw response.",
                        evidence_level="hypothesis"),
            ExplainStep(text="Problem-specific effect: the pattern may exist only for this operand pair.",
                        evidence_level="hypothesis"),
        ]
    else:
        possible.append(ExplainStep(
            text="The run's output differs in length or timing from its peers for an unknown reason.", evidence_level="hypothesis"))
        alternatives.append(ExplainStep(text="Ordinary variation in latency or output length.", evidence_level="hypothesis"))

    demo = None
    if exp.is_demo_data:
        demo = ("DEMO / MOCK DATA: this experiment ran on the deterministic mock model, which injects wrong answers on "
                "purpose. Nothing here describes a real LLM.")
    return ExplainOut(failure=fo, observed=observed, controlled_variables=controls, changed_variable=changed,
                      follow_ups=follow, evidence=evidence, possible_explanations=possible,
                      alternative_explanations=alternatives, limitations=LIMITATIONS, demo_notice=demo)


async def lineage(session: AsyncSession, experiment_id: uuid.UUID) -> tuple[list[uuid.UUID], list[ExperimentLineage]]:
    """All experiments connected to this one (ancestors and descendants), and the edges between them."""
    seen: set[uuid.UUID] = {experiment_id}
    frontier = {experiment_id}
    edges: dict[uuid.UUID, ExperimentLineage] = {}
    while frontier:
        found = list((await session.execute(select(ExperimentLineage).where(
            ExperimentLineage.parent_experiment_id.in_(frontier) | ExperimentLineage.child_experiment_id.in_(frontier)))).scalars())
        frontier = set()
        for e in found:
            edges[e.id] = e
            for n in (e.parent_experiment_id, e.child_experiment_id):
                if n not in seen:
                    seen.add(n)
                    frontier.add(n)
    return list(seen), list(edges.values())
