# Testing

| Layer | What | Count / result | How to run |
|---|---|---|---|
| Backend unit + integration + API | evaluators, statistics (reference values), adapters (HTTP adapters against simulated servers; Hugging Face adapter against stand-ins), engine (retry, timeout, cancel, resume, concurrency), the five experiment types and the constraint checker, anomaly detection, clustering, comparison, reports, exports, notebook, authentication, authorization, security, query-count guards, CLI | **230 tests, 97% line coverage** | `cd backend && pytest --cov=app` |
| Lint and types | ruff, mypy | clean on 93 source files | `ruff check . && mypy app` |
| Frontend component | rendering, auth flow, visibility controls, evidence drill-down, Markdown safety | **27 tests** | `cd frontend && npm test` |
| Browser end-to-end | real Chromium: run an experiment from the form, expand evidence, generate a report, create an account, private experiment hidden after sign-out, phone layout, console errors | **9 steps, all pass** | `cd e2e && npm i && node e2e.mjs` |
| Responsive audit | 12 pages at 360, 768, 1024 and 1440 px: horizontal overflow, elements wider than the viewport, console errors | **no problems** | `cd e2e && IDS_JSON=ids.json node audit.mjs` |
| Smoke test | any deployment, standard library only | 10 checks | `python scripts/smoke_test.py <url>` |
| Dependency audit | pip-audit, npm audit | no known vulnerabilities in runtime dependencies | see SECURITY.md |
| Secret scan | tracked files | clean | `python scripts/scan_secrets.py` |

Coverage note: SQLAlchemy's async layer runs on greenlets, so `pyproject.toml` sets `concurrency = ["greenlet", "thread"]`.
Without it coverage reports about 84% instead of the true figure.

## Required scenarios (from the project brief)
Invalid input (validation, bad templates, hostile ids), API failure (unreachable server, 4xx/5xx handling), model timeout,
empty responses, duplicate experiments, cancellation, retry and resume, authentication (tokens: forged, expired, unsigned,
wrong type), authorization (every data endpoint, as owner, stranger, anonymous), rate limiting (per IP, auth endpoints),
request-size limits, hostile model output in reports and CSV.

## What is not covered, honestly
- **No real language model has been run.** The Hugging Face adapter is tested against stand-ins, which shows it calls the
  library correctly, not that a real model loads and answers. Ollama and OpenAI-compatible adapters are tested against
  simulated servers.
- **PostgreSQL** has not been exercised by the test suite (SQLite is used); migrations use portable types. The Docker image
  and `docker compose` have not been built or run in the environment where this was developed.
- **The CI workflow** (`.github/workflows/ci.yml`) parses but has not run on GitHub.
- Browser tests ran in Chromium only, on Linux.
- Mock-model results exercise the pipeline and are not evidence about any real model.
