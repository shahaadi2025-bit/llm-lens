"""Research report for one experiment, generated deterministically from stored data (no LLM involved).

Rules baked in: every number carries n, interval and method; statements carry an evidence level; a reproduced anomaly is
called an association, never a cause; small samples are not interpreted; mock data is labelled at the top and in the
conclusion; no internal mechanism is ever asserted.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.experiments.registry import get_experiment_type
from app.models import (
    Experiment,
    ExperimentLineage,
    ExperimentRun,
    FailureMode,
    LLMModel,
    Metric,
    ModelVersion,
    Prompt,
    Response,
)
from app.reports.markdown_utils import interval, md_code, md_text, pct, table
from app.services.metrics import load_rows
from app.statistics.sensitivity import MIN_BLOCKS_FOR_INFERENCE, analyse

DEMO_BANNER = ("> **DEMO / MOCK DATA.** This experiment ran on a deterministic mock model that injects wrong answers on "
               "purpose. Nothing below describes a real language model and none of it is experimental evidence.\n")
GENERIC_LIMITS = [
    "Black-box observation: results describe this model's outputs on these prompts and settings, not its internal mechanisms.",
    "Intervals are Wilson 95% for proportions; small samples give wide intervals.",
    "Tests are exploratory and not corrected for multiple comparisons.",
    "At temperature 0 a deterministic model repeats itself, so repetitions mostly test prompt forms, not randomness.",
    "The evaluator extracts the last number in a response; unusual answer formats can be mis-scored.",
]


async def build_experiment_report(session: AsyncSession, exp: Experiment) -> tuple[str, str, bool]:
    mv = await session.get(ModelVersion, exp.model_version_id)
    model = await session.get(LLMModel, mv.model_id) if mv else None
    try:
        etype = get_experiment_type(exp.task_type)
        type_title, type_desc = etype.title, etype.description
    except KeyError:
        type_title, type_desc = exp.task_type, ""
    demo = exp.is_demo_data
    rows = await load_rows(session, exp.id, exp.task_type)
    metrics = list((await session.execute(select(Metric).where(Metric.experiment_id == exp.id).order_by(Metric.name))).scalars())
    runs = list((await session.execute(select(ExperimentRun).where(ExperimentRun.experiment_id == exp.id))).scalars())
    counts = {s: sum(1 for r in runs if r.status == s) for s in ("succeeded", "failed", "cancelled", "pending", "running")}
    acc = next((m for m in metrics if m.name == "accuracy"), None)
    paired = [(r.group, r.block, r.passed) for r in rows if r.group and r.block]
    ana = analyse(paired) if paired else None

    L: list[str] = [f"# Research report: {md_text(exp.name, 150)}\n"]
    if demo:
        L.append(DEMO_BANNER)
    L.append(f"*Generated from stored data for experiment `{exp.id}` (status: {exp.status}). Created {exp.created_at:%Y-%m-%d %H:%M} UTC.*\n")

    L += ["## 1. Research question\n", md_text(exp.research_question, 1000) + "\n"]
    L += ["## 2. Hypothesis\n", (md_text(exp.hypothesis, 1000) if exp.hypothesis else
                                  "No hypothesis was stated before the run. Results are exploratory.") + "\n"]
    L += ["## 3. Methodology\n",
          f"- Experiment type: **{md_text(type_title)}**. {md_text(type_desc, 400)}",
          f"- Prompts are generated deterministically from the configuration and seed {exp.seed}, so the same configuration reproduces the same prompts.",
          f"- Evaluator: `{exp.evaluator}` (deterministic: scores are computed by code, not by another model).",
          f"- Sampling: temperature {exp.temperature}, max tokens {exp.max_tokens}, {exp.repetitions} repetition(s).",
          "- Failure handling: each run has a timeout and bounded retries; runs that still fail are recorded as failed and excluded from metrics.\n"]
    L += ["## 4. Model\n",
          f"- Model: `{model.slug if model else '?'}` ({md_text(model.display_name) if model else '?'}), provider `{model.provider if model else '?'}`",
          f"- Version: `{mv.version_label if mv else '?'}`" + (f", revision `{mv.revision}`" if mv and mv.revision else ""),
          f"- Context length: {model.context_length if model else '?'} tokens" + (" (mock model)" if demo else "") + "\n"]
    L += ["## 5. Dataset\n",
          (f"{md_text(exp.dataset_name)} (version {md_text(exp.dataset_version or 'n/a')})" if exp.dataset_name else
           "No external dataset. Prompts are generated from the configuration below.") + "\n"]
    L += ["## 6. Experimental configuration\n", "```json", _json(exp.config), "```\n"]

    L += ["## 7. Results\n",
          f"Runs: {counts['succeeded']} succeeded, {counts['failed']} failed, {counts['cancelled']} cancelled, "
          f"{counts['pending'] + counts['running']} unfinished. Metrics use succeeded runs only.\n"]
    L.append(table(["Metric", "Value", "95% interval", "n", "Method"], [
        [m.name, pct(m.value) if (m.name == "accuracy" or m.name.endswith("_rate") or m.name.startswith("accuracy[")) else f"{m.value:.2f}",
         interval(m.ci_low, m.ci_high) if m.name != "latency_ms_mean" else f"[{m.ci_low:.1f}, {m.ci_high:.1f}]" if m.ci_low is not None else "n/a",
         str(m.n), m.method] for m in metrics if not m.name.startswith("accuracy[")]))
    if ana and ana.groups:
        L += ["\nAccuracy by prompt form:\n", table(["Form", "Accuracy", "95% interval (Wilson)", "n"], [
            [g, pct(i.estimate), interval(i.low, i.high), str(i.n)] for g, i in ana.groups.items()])]

    L.append("## 8. Statistical analysis\n")
    if ana and ana.statements:
        if ana.cochran_q is not None:
            L.append(f"Cochran's Q across {len(ana.groups)} forms: Q = {ana.cochran_q:.2f}, df = {ana.cochran_df}, "
                     f"p = {ana.cochran_p:.3g}, {ana.n_blocks} complete problem sets. Effect size (Cohen's h, best vs worst form): "
                     f"{ana.cohens_h:.2f}.\n")
        L += [f"- [{s.evidence_level}] {md_text(s.text, 600)}" for s in ana.statements]
        L.append("")
    else:
        L.append("No comparison across prompt forms applies to this experiment, or there are no evaluated runs.\n")

    flagged = list((await session.execute(
        select(FailureMode, Prompt, Response).join(ExperimentRun, ExperimentRun.id == FailureMode.run_id)
        .join(Prompt, Prompt.run_id == ExperimentRun.id).outerjoin(Response, Response.run_id == ExperimentRun.id)
        .where(ExperimentRun.experiment_id == exp.id, FailureMode.label == "representation_sensitivity")
        .order_by(ExperimentRun.run_index).limit(10))).all())
    L.append("## 9. Failure cases\n")
    if flagged:
        L.append("Potential anomalies (the same problem answered correctly in some forms and incorrectly in others). "
                 "These are flags, not confirmed failures.\n")
        L.append(table(["Status", "Form", "Prompt", "Response", "Expected"], [
            [f.status.replace("_", " "), md_text(f.details.get("failed_group", "?")), md_code(p.text, 80),
             md_code(r.text if r else "", 80), md_text(p.expected_answer or "")] for f, p, r in flagged]))
    else:
        L.append("No form-sensitivity anomalies were flagged.\n")

    edges = list((await session.execute(select(ExperimentLineage).where(
        ExperimentLineage.parent_experiment_id == exp.id, ExperimentLineage.trigger_run_id.is_not(None)))).scalars())
    verdicts = []
    for e in edges:
        fm = (await session.execute(select(FailureMode).where(FailureMode.run_id == e.trigger_run_id,
                                                              FailureMode.detector == "paired_discordance"))).scalar_one_or_none()
        child = await session.get(Experiment, e.child_experiment_id)
        if fm and child:
            verdicts.append((fm, child))
    reproduced = [(fm, c) for fm, c in verdicts if fm.status == "reproduced"]
    L.append("## 10. Potential explanations\n")
    L.append("All items below are hypotheses, not findings.\n")
    if reproduced:
        for fm, c in reproduced:
            ev = fm.details.get("followup_evidence", {})
            L.append(f"- [correlation] Follow-up `{c.name}`: the failing form `{md_text(fm.details.get('failed_group', '?'))}` was "
                     f"incorrect in {ev.get('form_failures')}/{ev.get('form_runs')} follow-up runs versus "
                     f"{ev.get('other_failures')}/{ev.get('other_runs')} for the other forms (evidence strength: {ev.get('strength')}). "
                     "This is a reproduced association between prompt form and correctness for that problem; it is not an identified cause.")
    elif verdicts:
        L.append("- Follow-up experiments did not reproduce the flagged behavior; the original errors are consistent with chance variation (not proven).")
    else:
        L.append("- [hypothesis] If prompt form matters for this model, correctness should differ between forms for the same problem; "
                 "this experiment alone cannot establish that. Run follow-ups from the flagged cases.")
    L.append("")
    L += ["## 11. Alternative explanations\n",
          "- Sampling variability: a single incorrect answer among several forms can occur by chance.",
          "- Evaluator artifact: the last-number rule may mis-score a correct answer in an unusual format (check raw responses).",
          "- Problem-specific effects: a pattern may hold only for particular operands.",
          "- Small sample: few problems give wide intervals and low power."
          + ("\n- Mock model: wrong answers here were injected by design." if demo else "") + "\n"]
    L += ["## 12. Limitations\n"] + [f"- {x}" for x in GENERIC_LIMITS]
    if ana and ana.n_blocks < MIN_BLOCKS_FOR_INFERENCE and ana.n_blocks:
        L.append(f"- Only {ana.n_blocks} complete problem sets (fewer than {MIN_BLOCKS_FOR_INFERENCE}): differences between forms are not interpreted.")
    L.append("")

    env = exp.environment or {}
    L += ["## 13. Reproducibility information\n", table(["Item", "Value"], [
        ["Experiment ID", f"`{exp.id}`"], ["Seed", str(exp.seed)], ["Specification hash", f"`{exp.spec_hash[:16]}…`" if exp.spec_hash else "n/a"],
        ["Software version", exp.software_version], ["Python", md_text(str(env.get("python", "n/a")))],
        ["Platform", md_text(str(env.get("platform", "n/a")), 120)],
        ["Libraries", md_text(", ".join(f"{k} {v}" for k, v in (env.get("libraries") or {}).items()) or "n/a", 200)],
        ["Hardware", md_text(f"{(env.get('hardware') or {}).get('recommended_device', 'n/a')}, {(env.get('hardware') or {}).get('cpu_count', '?')} CPUs", 100)],
        ["Started / finished (UTC)", f"{exp.started_at:%Y-%m-%d %H:%M:%S}" + (f" / {exp.finished_at:%H:%M:%S}" if exp.finished_at else "") if exp.started_at else "n/a"],
    ])]
    L.append("To rerun: clone this experiment in the app, or `llm-lens run <template.yaml>` with the configuration above.\n")

    L.append("## 14. Conclusion\n")
    if counts["succeeded"] == 0 or acc is None:
        L.append("No evaluated runs: this experiment produced no results to conclude from.")
    else:
        L.append(f"On {acc.n} evaluated runs the model answered {pct(acc.value)} correctly (95% CI {interval(acc.ci_low, acc.ci_high)}).")
        level = "observation"
        if ana and ana.best is not None:
            if ana.n_blocks < MIN_BLOCKS_FOR_INFERENCE:
                L.append(f"The number of problems ({ana.n_blocks}) is too small to say whether prompt form matters.")
            elif ana.cochran_p is not None and ana.cochran_p < 0.05:
                L.append("Success rates differed between prompt forms in this sample (exploratory test).")
                level = "correlation"
            else:
                L.append("No reliable difference between prompt forms was detected, which is not evidence that none exists.")
        if reproduced:
            level = "correlation"
            L.append(f"{len(reproduced)} flagged anomaly(ies) reproduced in follow-up experiments: an association, not a cause.")
        L.append(f"\nStrongest evidence level reached: **{level}**. No supported conclusion about the model's internal mechanisms is "
                 "possible from black-box experiments.")
    if demo:
        L.append("\n*This conclusion concerns a mock model and is not a finding about any real language model.*")
    L.append("")
    return f"Research report: {exp.name}", "\n".join(L), demo


def _json(obj: object) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=True, default=str)


