# Evaluation

Deterministic evaluators are preferred wherever the answer can be checked by code.

| Evaluator | Kind | Rule |
|---|---|---|
| `exact_match` | deterministic | whitespace/case-insensitive equality |
| `numeric_match` | deterministic | last number in the response equals the expected number exactly |
| `constraint_check` | deterministic | JSON list of constraints (word limit, include/exclude word, lowercase, starts/ends with, sentence count); score = fraction satisfied, pass = all |

`numeric_match` known limitation: a correct number followed by an unrelated number is scored incorrect. The
extraction rule is stored in each evaluation's `details`.

LLM judges (not implemented) must be stored with `kind = llm_judge`, judge model, prompt, version and criteria,
shown as "LLM-based evaluation", and never treated as ground truth.

Mock mode: the mock model gets about 15% of multiplications wrong on purpose (hash-based, deterministic) so the
pipeline exercises both outcomes. Those results are demo data, flagged `is_demo_data`, not evidence about any LLM.
