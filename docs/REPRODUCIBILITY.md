# Reproducibility and statistics

Every experiment stores: prompts (deterministic from config + seed), model and version, temperature, max tokens,
seed, repetitions, evaluator and version, software version, Python/library versions, hardware, timestamps.
"Clone" creates an identical experiment (same spec hash); "Rerun/Resume" re-executes unfinished runs.

## Statistics used
| Quantity | Method | Why |
|---|---|---|
| Accuracy / rates | Wilson score interval, 95% | Reliable for small n and values near 0 or 1 |
| Means (latency) | Seeded percentile bootstrap, 10,000 resamples | No normality assumption; same data gives the same interval |
| Difference between two proportions | Cohen's h | Effect size, independent of n |
| Same problems in k forms | Cochran's Q (McNemar exact for two forms) | Paired binary outcomes |
| Association | Spearman (default) or Pearson | Rank-based is robust to outliers |

Rules the UI and API follow: every number ships with n, interval and method; interpretation statements are tagged
observation / correlation (never hypothesis or supported conclusion until follow-up experiments exist); tests are
labelled exploratory; with fewer than 10 complete problem sets the analysis refuses to interpret differences; and no
statement claims an internal mechanism.

Every metric links to the runs it was computed from (`metric_evidence`), so any number can be re-derived by hand.
