# Experiments

Every experiment type documents its research question, how prompts are generated (deterministically from the
seed), and which evaluator scores them. Add a type by subclassing `ExperimentType` in
`backend/app/experiments/types/` and registering it in `backend/app/experiments/registry.py`.

## arithmetic_representation (implemented)
**Research question:** Does the correctness of a model's answer to the same multiplication change with the
surface representation of the problem (operand order, operator symbol, wording)?

Each operand pair (the anchor pair 37 and 84, plus seeded random 2-digit pairs) is asked in six equivalent forms:
`a × b`, `b × a`, `a * b`, `b * a`, `a groups of b`, `b groups of a`. All forms have the same expected product.
Evaluator: `numeric_match` (deterministic, last number in the response, exact comparison).

**Interpretation limits:** a difference between forms is an observation about one model on these prompts. It does
not identify an internal cause, and with few pairs it may be noise. Statistics with intervals arrive in Phase 3.

## prompt_sensitivity (implemented)
**Research question:** Does the correctness of a model's answer to the same multiplication change when the prompt's
surface form is changed (paraphrase, capitalization, formatting, sentence order, irrelevant context, an example)?

Mutations are deterministic (see `backend/app/experiments/mutations.py`): `base` (reference), `instruction_first`,
`uppercase`, `lowercase`, `markdown_format`, `extra_whitespace`, `irrelevant_context`, `few_shot_example`, `paraphrase`
(rule-based template, not an LLM paraphrase). Each run records which single change was applied.

## Anomalies and follow-ups
After every experiment, detectors flag POTENTIAL anomalies (never "model failure"):
- `paired_discordance`: the same problem correct in some forms, incorrect in others. Triggers follow-ups.
- `iqr` (k=3), `zscore` (>3), `isolation_forest`: outliers in latency / response length. The dashboard counts a run
  only when two or more outlier methods agree, because Isolation Forest flags a fixed fraction of any data.

A follow-up re-asks the same problem in every original form with several new seeds (6, or fewer to fit the run limit).
Verdict rule (see `followup_evidence.py`): reproduced if the failing form fails in >= half its follow-up runs and its
Wilson 95% lower bound exceeds the other forms' failure rate; strength strong / moderate / weak by that lower bound
(>= 0.6 / >= 0.4 / otherwise). Even a reproduced result is labelled `correlation`, never a supported conclusion, and
never an internal mechanism.

Planned types (not implemented): instruction following, context length, long-context
retrieval, consistency, multilingual, false premise, tool use.
