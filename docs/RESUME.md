# Resume and interview positioning

Everything below is true of the current repository. Replace nothing with larger numbers; add real-model results only after you
have run a real model and can show the report.

## Three versions

**One line**
> Built LLM Lens, a reproducible black-box LLM experimentation platform (FastAPI, React/TypeScript, PostgreSQL) for studying prompt sensitivity and failure modes with controlled experiments, statistical evaluation, anomaly detection and behavioral fingerprinting.

**Standard (3 bullets)**
- Developed LLM Lens, a reproducible black-box LLM experimentation platform: provider-independent model adapters, an experiment engine with bounded concurrency, retry, cancellation and resume, five experiment types (prompt sensitivity, instruction ordering, long-context retrieval and needle position among them) scored by deterministic evaluators, and automated follow-up experiments that test whether a flagged anomaly reproduces.
- Implemented the statistics and analysis layer (Wilson, bootstrap and Newcombe intervals, Cochran's Q, McNemar, effect sizes; IQR, z-score and Isolation Forest anomaly detection; silhouette-selected clustering) with every metric traceable to the prompts, responses and evaluator verdicts behind it, and generated research reports that state evidence levels and never claim internal mechanisms.
- Engineered the platform end to end: accounts with enforced private/public access on every endpoint, public-demo abuse limits, CLI, free-tier deployment, 230 automated backend tests (97% line coverage), 27 component tests and a real-browser end-to-end suite; found and removed N+1 queries (201 → 5 SQL statements on a list endpoint) using a benchmark script.

**Short project-section description**
> LLM Lens: a research tool for studying language models as black boxes. Controlled experiments, interval estimates on every number, anomalies treated as hypotheses to test, and reports that separate observation from correlation from conclusion. Python, FastAPI, SQLAlchemy, React, TypeScript, scikit-learn, Docker.

## Interview talking points
- **The design principle:** a black-box experiment can show that behavior changed, never why inside the model. The report generator, the explain view and the follow-up rule all enforce that; be ready to show the "Explain this failure" page.
- **A decision with a trade-off:** clustering defaults to TF-IDF rather than neural embeddings because PyTorch does not fit a free 512 MB container; sentence embeddings are an opt-in backend.
- **A bug the tests caught:** cloning a public experiment inherited its visibility, which would have made someone's clone public by default; fixed so clones are always private.
- **A bug the benchmark caught:** per-row queries in list endpoints, invisible at small sizes; fixed by batching, with regression tests that assert a constant query count.
- **A measurement mistake worth admitting:** the first coverage reading (84%) was wrong because async SQLAlchemy runs on greenlets; the corrected figure is 97%.
- **Security you can explain:** scrypt hashing, signed tokens that reject unsigned and wrong-type tokens, 404-not-403 for hidden resources, CSV formula neutralisation, escaped model output in reports.

## Say plainly
- All results shown so far come from a deterministic mock model with injected errors; the platform's purpose is shown, not a finding about any real model.
- Four of eight fingerprint dimensions are measurable, and four of ten planned experiments are not built.
- Docker, PostgreSQL and the CI workflow were written but not run in the development environment.
If you run a real model before an interview, add one real report and say what it does and does not show.
