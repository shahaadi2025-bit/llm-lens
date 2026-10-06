# Performance

Measured with `scripts/benchmark.py` (run from `backend/`: `python ../scripts/benchmark.py 40`). It seeds a temporary database
through the real API (40 experiments, 1,440 runs, mock model), then times each endpoint (median and 90th percentile of 7
calls) and counts SQL statements per request. It runs in-process, so it measures application and database cost only.

**Caveats.** SQLite, not PostgreSQL; mock model, not a real LLM (so engine throughput is the platform's overhead, not model
speed); one machine, one run. Use the numbers to find N+1 queries and relative cost, not as production figures.

## Results (40 experiments, 1,440 runs)
| Endpoint | p50 ms | p90 ms | SQL statements |
|---|---|---|---|
| GET /experiments (25) | 9.2 | 10.3 | 5 |
| GET /experiments?limit=100 | 10.2 | 10.7 | 5 |
| GET /dashboard | 15.1 | 18.1 | 11 |
| GET /experiments/{id} (36 runs with evidence) | 10.3 | 12.8 | 9 |
| GET /experiments/{id}/metrics | 7.9 | 9.8 | 11 |
| GET /experiments/{id}/analysis | 4.8 | 5.0 | 2 |
| GET /failures (50 rows) | 10.1 | 10.5 | 5 |
| GET /failures/{id}/explain | 8.4 | 9.6 | 11 |
| GET /failure-clusters | 2.7 | 3.0 | 1 |
| GET /fingerprints/{model} | 5.1 | 6.1 | 2 |
| GET /compare | 6.8 | 6.9 | 6 |
| GET /exports/experiments/{id}/runs.csv | 5.1 | 5.6 | 2 |
| GET /exports/experiments.csv | 8.1 | 8.4 | 5 |
| POST /reports | 15.9 | 15.9 | 9 |
| POST /failure-clusters/recompute | 514 | 514 | 27 |

Engine: 40 experiments (1,440 runs) created, run and analysed in 19.2 s, which is 125 experiments per minute and 75 runs per
second with the mock model; 0 failed runs. Failure rate, latency, tokens per second and experiments per minute are also
tracked from stored data for real models (run latency and token counts are stored per run).

## What the benchmark found and fixed
The first measurement showed N+1 queries (one query per row), invisible at small data sizes:

| Endpoint | Before | After |
|---|---|---|
| GET /failures (50 rows) | 120 ms, 201 statements | 10 ms, 5 statements |
| GET /exports/experiments.csv | 101 ms, 121 statements | 8 ms, 5 statements |
| GET /experiments?limit=100 | 43 statements | 5 statements |

Related rows are now loaded in batches, and `tests/test_performance.py` asserts that these endpoints cost the same number of
queries for 3 rows as for 100, so the regression cannot return unnoticed.

## Known costs
- Recomputing failure clusters takes about half a second here (k-means over several cluster counts plus silhouette scores);
  it is a manual action on its own button, not a page-load cost. It scales with the number of incorrect answers (capped at 2,000).
- The dashboard loads flagged-run details to count distinct anomalies; at tens of thousands of runs it should become an
  aggregate query.
- Public deployment uses an in-process rate limiter and a single container: fine for a demo, not for horizontal scale.
- Not yet done: PostgreSQL benchmarks, caching beyond the database's own, and load testing with concurrent users.
