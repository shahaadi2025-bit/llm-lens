# Research report: Arithmetic representation sensitivity

> **DEMO / MOCK DATA.** This experiment ran on a deterministic mock model that injects wrong answers on purpose. Nothing below describes a real language model and none of it is experimental evidence.

*Generated from stored data for experiment `6aed1015-e588-4773-bd5e-efaa55d05c43` (status: completed). Created 2026-10-04 11:50 UTC.*

## 1. Research question

Does the correctness of a model's answer to the same multiplication change with the surface representation of the problem (operand order, operator symbol, wording)?

## 2. Hypothesis

Untested: accuracy differs between forms for at least some operand pairs. The null (no difference) is equally plausible.

## 3. Methodology

- Experiment type: **Arithmetic representation sensitivity**. Each operand pair is asked in several equivalent forms. A difference between forms is an observation about this model on these prompts; it does not identify an internal cause.
- Prompts are generated deterministically from the configuration and seed 7, so the same configuration reproduces the same prompts.
- Evaluator: `numeric_match` (deterministic: scores are computed by code, not by another model).
- Sampling: temperature 0.0, max tokens 64, 1 repetition(s).
- Failure handling: each run has a timeout and bounded retries; runs that still fail are recorded as failed and excluded from metrics.

## 4. Model

- Model: `mock-deterministic-v1` (Mock v1 (deterministic, not a real LLM)), provider `mock`
- Version: `mock-1`
- Context length: 4096 tokens (mock model)

## 5. Dataset

No external dataset. Prompts are generated from the configuration below.

## 6. Experimental configuration

```json
{
  "n_random_pairs": 5,
  "representations": [
    "a_x_b",
    "b_x_a",
    "a_star_b",
    "b_star_a",
    "a_groups_of_b",
    "b_groups_of_a"
  ]
}
```

## 7. Results

Runs: 36 succeeded, 0 failed, 0 cancelled, 0 unfinished. Metrics use succeeded runs only.

| Metric | Value | 95% interval | n | Method |
|---|---|---|---|---|
| accuracy | 94.4% | [81.9%, 98.5%] | 36 | wilson-95 |
| empty_response_rate | 0.0% | [0.0%, 9.6%] | 36 | wilson-95 |
| latency_ms_mean | 97.88 | [44.1, 192.4] | 36 | bootstrap-percentile-10000-seed0 |


Accuracy by prompt form:

| Form | Accuracy | 95% interval (Wilson) | n |
|---|---|---|---|
| a_groups_of_b | 100.0% | [61.0%, 100.0%] | 6 |
| a_star_b | 83.3% | [43.6%, 97.0%] | 6 |
| a_x_b | 100.0% | [61.0%, 100.0%] | 6 |
| b_groups_of_a | 100.0% | [61.0%, 100.0%] | 6 |
| b_star_a | 100.0% | [61.0%, 100.0%] | 6 |
| b_x_a | 83.3% | [43.6%, 97.0%] | 6 |

## 8. Statistical analysis

Cochran's Q across 6 forms: Q = 4.00, df = 5, p = 0.549, 6 complete problem sets. Effect size (Cohen's h, best vs worst form): 0.84.

- [observation] Accuracy ranged from 83% (a_star_b) to 100% (a_groups_of_b) across 6 forms, 36 runs in total.
- [observation] Only 6 complete problem sets: too few to say whether form differences are more than chance. Add problems before interpreting differences.

## 9. Failure cases

Potential anomalies (the same problem answered correctly in some forms and incorrectly in others). These are flags, not confirmed failures.

| Status | Form | Prompt | Response | Expected |
|---|---|---|---|---|
| potential anomaly | b_x_a | `What is 21 × 18? Reply with only the number.` | `The answer is 376.` | 378 |
| potential anomaly | a_star_b | `58 * 86 = ? Reply with only the number.` | `The answer is 4984.` | 4988 |

## 10. Potential explanations

All items below are hypotheses, not findings.

- [hypothesis] If prompt form matters for this model, correctness should differ between forms for the same problem; this experiment alone cannot establish that. Run follow-ups from the flagged cases.

## 11. Alternative explanations

- Sampling variability: a single incorrect answer among several forms can occur by chance.
- Evaluator artifact: the last-number rule may mis-score a correct answer in an unusual format (check raw responses).
- Problem-specific effects: a pattern may hold only for particular operands.
- Small sample: few problems give wide intervals and low power.
- Mock model: wrong answers here were injected by design.

## 12. Limitations

- Black-box observation: results describe this model's outputs on these prompts and settings, not its internal mechanisms.
- Intervals are Wilson 95% for proportions; small samples give wide intervals.
- Tests are exploratory and not corrected for multiple comparisons.
- At temperature 0 a deterministic model repeats itself, so repetitions mostly test prompt forms, not randomness.
- The evaluator extracts the last number in a response; unusual answer formats can be mis-scored.
- Only 6 complete problem sets (fewer than 10): differences between forms are not interpreted.

## 13. Reproducibility information

| Item | Value |
|---|---|
| Experiment ID | `6aed1015-e588-4773-bd5e-efaa55d05c43` |
| Seed | 7 |
| Specification hash | `7f3b9d24c8f537fd…` |
| Software version | 0.1.0 |
| Python | 3.14.0 |
| Platform | Windows-11-10.0.26200-SP0 |
| Libraries | fastapi 0.142.2, sqlalchemy 2.1.3, numpy 2.5.3, scipy 1.18.1 |
| Hardware | cpu, 12 CPUs |
| Started / finished (UTC) | 2026-10-04 11:50:35 / 11:50:37 |

To rerun: clone this experiment in the app, or `llm-lens run <template.yaml>` with the configuration above.

## 14. Conclusion

On 36 evaluated runs the model answered 94.4% correctly (95% CI [81.9%, 98.5%]).
The number of problems (6) is too small to say whether prompt form matters.

Strongest evidence level reached: **observation**. No supported conclusion about the model's internal mechanisms is possible from black-box experiments.

*This conclusion concerns a mock model and is not a finding about any real language model.*
