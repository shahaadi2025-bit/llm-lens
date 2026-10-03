"""Generate a controlled follow-up from a flagged anomaly. The anomaly is a question, not a conclusion."""
from app.core.config import Settings
from app.experiments.registry import get_experiment_type
from app.models import Experiment, FailureMode
from app.schemas.experiment import ExperimentCreate

FOLLOWUP_SEED_OFFSET = 1000


class FollowUpNotSupported(ValueError):
    pass


def build_followup(exp: Experiment, failure: FailureMode, settings: Settings) -> ExperimentCreate:
    """Re-ask the SAME problem in ALL the original forms, several times, so one unlucky answer cannot masquerade
    as a pattern. Only the repetition seeds change; everything else is held constant."""
    if failure.detector != "paired_discordance":
        raise FollowUpNotSupported(
            "Follow-ups are generated for form-sensitivity anomalies. Statistical outliers have no controlled "
            "follow-up yet; inspect the run's evidence instead.")
    pair = failure.details.get("pair")
    form = failure.details.get("failed_group")
    if not pair or not form:
        raise FollowUpNotSupported("This anomaly lacks the problem/form needed to build a follow-up.")
    try:
        etype = get_experiment_type(exp.task_type)
    except KeyError as exc:
        raise FollowUpNotSupported(str(exc)) from exc

    forms_key = "representations" if exp.task_type == "arithmetic_representation" else "kinds"
    forms = exp.config.get(forms_key) or etype.default_config[forms_key]
    n_forms = len(forms) + (1 if exp.task_type == "prompt_sensitivity" else 0)  # prompt_sensitivity adds 'base'
    reps = max(2, min(6, settings.effective_max_runs // max(n_forms, 1)))
    a, b = pair
    passing = ", ".join(failure.details.get("passing_groups", []))
    return ExperimentCreate(
        name=f"Follow-up: {a}×{b} in form '{form}'", task_type=exp.task_type, temperature=exp.temperature,
        max_tokens=exp.max_tokens, seed=exp.seed + FOLLOWUP_SEED_OFFSET, repetitions=reps, evaluator=exp.evaluator,
        config={"pairs": [[a, b]], forms_key: forms}, is_public=exp.is_public,
        research_question=(f"Does the incorrect answer to {a}×{b} in form '{form}' reproduce when the same problem is "
                           f"asked again in every original form with {reps} different seeds?"),
        hypothesis=(f"Hypothesis (untested): this model answers {a}×{b} less reliably in form '{form}' than in the "
                    f"forms it answered correctly ({passing}). Alternative: the original error was sampling variability."),
    )
