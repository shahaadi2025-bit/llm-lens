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
not identify an internal cause, and with few pairs it may be noise. Every result carries an interval (see REPRODUCIBILITY.md).

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

Planned types (not implemented, see the table at the end): instruction following, context length, long-context
retrieval, consistency, multilingual, false premise, tool use.

## instruction_ordering (implemented)
**Research question:** Does the model satisfy the same set of verifiable instructions equally often when they are listed in a
different order? Each task has 2 to 5 machine-checkable constraints (word limit, required or forbidden word, lowercase,
opening text, closing text, sentence count). The same constraints are presented as listed, reversed, rotated and shuffled.
Evaluator `constraint_check` (deterministic): score = fraction satisfied; an answer passes only if every constraint holds.
Fingerprint dimension I. Analysis: Cochran's Q across orderings over the same tasks.

## context_position and context_length (implemented)
**context_position:** does retrieval accuracy depend on where in a long context a fact sits (0, 10, 25, 50, 75, 90, 100 percent)?
**context_length:** does it change as the context gets longer? A target fact (an access code for one named vault) is placed
among digit-free filler sentences and decoy facts about other vaults; the answer is checked exactly (`numeric_match`).
Sizes are approximate tokens (about 4 characters each). A size the chosen model's window cannot fit is rejected at creation
and never attempted. Total prompt characters are capped per deployment. Fingerprint dimension C. Charts list positions and
sizes in numeric order, and the analysis refuses to interpret fewer than 10 complete trials.

**Mock behavior:** in mock mode both new types are answered by a stand-in that slips at a uniform pseudo-random rate. It has
**no** ordering or position effect built in, so any pattern a real model shows will be its own.

## Failure clustering
`POST /api/failure-clusters/recompute` clusters every incorrect answer (up to the newest 2000). Each answer is first
classified by a rule-based taxonomy (`empty_response`, `no_numeric_answer`, `numeric_near_miss` within 1%,
`numeric_far_miss`, `wrong_text`). Text is embedded (default: character n-gram TF-IDF with digits masked, which needs no
PyTorch and fits free-tier RAM; set `EMBEDDINGS_BACKEND=sentence-transformers` locally after installing
`requirements-ml.txt`), then k-means with k chosen by silhouette. k is capped so clusters average at least 4 members, and
if no structure separates (silhouette < 0.1) or there are fewer than 8 failures, everything stays in one cluster.
Cluster labels are computed from member facts (dominant error type and form); they describe the outputs, not their cause.
Only error types observable today exist; instruction-order, long-context, hallucination, contradiction and tool-use
clusters need their experiment types first.

## Fingerprint and comparison
Fingerprint dimensions: R M F C I H T S. Today M (arithmetic representation) and S (prompt sensitivity) can be measured;
the others are shown as "not measured", never as 0. Each measured dimension pools accuracy metrics (Wilson 95%) and links
to the experiments, then the runs, behind it.
Version comparison uses only completed experiments with an identical design (task, config, seed, settings, evaluator).
Difference interval: Newcombe hybrid-score 95% CI; effect size Cohen's h; exact McNemar on identical prompts
(exploratory). Statements never attribute a cause. In mock mode, `mock-deterministic-v1` (15% injected errors) and
`mock-deterministic-v2` (35%) exist so the comparison pipeline can be demonstrated; their difference is by construction.

## The ten initial experiments: what exists today
Every experiment must have a documented research question. Six are implemented; the rest are planned and listed so the
plan is explicit. Nothing marked "planned" has any code or results.

| # | Experiment | Research question | Status |
|---|---|---|---|
| 1 | Arithmetic representation sensitivity | Does correctness change with how the same multiplication is written? | **Implemented** (`arithmetic_representation`) |
| 2 | Instruction ordering sensitivity | Does the order of instructions in a prompt change whether constraints are satisfied? | **Implemented** (`instruction_ordering`) |
| 3 | Prompt paraphrase sensitivity | Does a controlled change to prompt wording, case, formatting or order change correctness? | **Implemented** (`prompt_sensitivity`) |
| 4 | Long-context retrieval | Does retrieval accuracy change as the context gets longer? | **Implemented** (`context_length`) |
| 5 | Context-position sensitivity | Does retrieval accuracy depend on where in the context the fact sits (0% to 100%)? | **Implemented** (`context_position`) |
| 6 | Repeated-answer consistency | Does the model give consistent answers to equivalent questions asked repeatedly? | Planned |
| 7 | False-premise handling | Does the model accept, challenge or invent around a false premise? | Planned |
| 8 | Multilingual consistency | Is behavior consistent across English, Hindi, Spanish, French, German and Chinese, allowing for translation effects? | Planned |
| 9 | Tool-use reliability | Does the model pick the right tool and arguments, in the right format? | Planned |
| 10 | Model-version comparison | Do two versions differ on identical prompts? | **Implemented** (matched-design comparison; templates `version_comparison_a/b.yaml`) |

Four fingerprint dimensions can be measured today (M, S, I, C). Reasoning, factuality, hallucination indicators and tool use are shown as not measured, never as zero.

## Templates and the command line
Templates live in `experiments/templates/*.yaml` (YAML mapping; `safe_load` only; unknown keys are rejected):
`name`, `task_type` (required), `research_question`, `hypothesis`, `model`, `seed`, `repetitions`, `temperature`,
`max_tokens`, `evaluator`, `config`, `is_public`.

```
pip install -e backend            # installs the `llm-lens` command
llm-lens --local health           # no server needed: own SQLite database (lens-cli.sqlite)
llm-lens --local run experiments/templates/arithmetic_representation.yaml --report report.md
llm-lens --local list
llm-lens --local inspect <id> --runs
llm-lens --local compare mock-deterministic-v1 mock-deterministic-v2
llm-lens --local export <id> --format csv -o runs.csv
llm-lens --api https://your-app.onrender.com login      # then use --api without --local
```
Without `--local` the CLI talks to any LLM Lens server (`--api` or `LLM_LENS_API`), authenticating with a token from
`llm-lens login`, `--token` or `LLM_LENS_TOKEN`. Exit codes: 0 success, 1 experiment failed/cancelled or not comparable,
2 usage or server error. For real models, set `MODEL_PROVIDER` and `MODEL_NAME` (for example Ollama) before running.

## Reports, exports and the notebook
- A research report has 14 fixed sections (research question, hypothesis, methodology, model, dataset, configuration,
  results, statistical analysis, failure cases, potential explanations, alternative explanations, limitations,
  reproducibility, conclusion). It is generated from stored data by code, not by an LLM. Statements carry an evidence
  level; the generator never awards "supported conclusion" and never states a cause or mechanism; samples with fewer than
  10 complete problem sets are not interpreted; mock data is labelled at the top and in the conclusion.
- Model output placed in a report is escaped (no HTML, no table breakage). CSV cells starting with `=`, `+`, `-`, `@` are
  prefixed with `'` so spreadsheets do not execute model output as formulas.
- Exports: JSON bundle per experiment, CSV of runs, CSV summary of visible experiments. PDF export is not implemented.
- Notebook: a private investigation holds a question, hypothesis, linked experiments, observations/notes/hypotheses, a
  conclusion and its limitations. A conclusion cannot be saved without limitations.
