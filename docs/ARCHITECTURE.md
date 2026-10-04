# LLM Lens: Architecture

## 1. Principle
Controlled experimentation + reproducibility + behavioral analysis. Every statement is tagged
observation, correlation, hypothesis or supported conclusion. A black-box experiment never claims an
internal mechanism.

## 2. System overview
```
Browser (React SPA)
   |  HTTPS, /api/*
   v
nginx (static files + reverse proxy)  ->  FastAPI (async)
                                             |-- API layer (auth, rate limits, validation)
                                             |-- Experiment engine (queue, concurrency, retry, cancel)
                                             |        |
                                             |        v
                                             |   ModelAdapter  -> mock | local HF | Ollama | OpenAI-compatible
                                             |-- Evaluators (deterministic first, LLM judge labelled)
                                             |-- Statistics, anomaly, clustering, reports
                                             v
                                         PostgreSQL (SQLite for dev/tests only)
```
The engine only ever talks to `ModelAdapter`, so providers are swappable.

## 3. Repository structure
See the tree in the README. Backend modules: `api/ core/ models/ schemas/ services/ experiments/
evaluators/ statistics/ anomaly/ clustering/ reports/`.

## 4. Technology decisions
| Choice | Reason |
|---|---|
| FastAPI + async SQLAlchemy 2 | Experiments are I/O-bound (model calls); async keeps the API responsive. |
| PostgreSQL primary, SQLite for tests | Production parity where it matters; fast tests. Migrations use portable types (JSON, Uuid, VARCHAR enums). |
| Alembic with batch mode | Same migrations run on SQLite and PostgreSQL. |
| Heavy ML deps split into `requirements-ml.txt` | Mock/public deployments stay small enough for free-tier containers. |
| Self-hosted fonts (fontsource) | No third-party requests; works offline in Docker. |
| Tailwind 3 | Stable, no extra build plugins. |

## 5. Database schema (implemented, migration `0001`)
users, models, model_versions, experiment_configs, experiments, experiment_lineage, experiment_runs,
prompts, responses, evaluations, metrics, metric_evidence, failure_modes, failure_clusters, reports.

Traceability chain: `metrics -> metric_evidence -> experiment_runs -> prompts / responses / evaluations`.
Lineage: `experiment_lineage(parent, child, trigger_run, relation)` forms the investigation graph.
`experiments.is_demo_data` marks rows that are NOT real LLM evidence; reports carry `includes_demo_data`.
Evaluations store judge model, prompt, version and criteria when `kind = llm_judge`.
Planned for Phase 7: notebook tables (investigations, notes).

## 6. Core interfaces (Phase 2)
- `ModelAdapter`: `generate()`, `stream()`, `get_model_info()`, `estimate_tokens()`.
- `Evaluator`: `evaluate(prompt, response, expected) -> Evaluation` (deterministic ones first).
- `ExperimentType`: builds prompt variants, picks evaluator, defines metrics and fingerprint dimension.

## 7. API structure
Prefix `/api`. Implemented: `GET /health`, `GET /experiment-types`, `POST|GET /experiments`, `GET /experiments/{id}`, `POST /experiments/{id}/run|cancel|clone`, `GET /models`, `GET /models/{id}`, `GET /system/hardware`, `GET /experiments/{id}/metrics`, `GET /experiments/{id}/analysis`, `GET /metrics/{id}/evidence`, `GET /dashboard`, `GET /failures`, `GET /failures/{id}/explain`, `POST /experiments/{id}/follow-up`, `GET /experiments/{id}/lineage`, `GET|POST /failure-clusters`, `GET /fingerprints/{model_id}`, `GET /model-versions`, `GET /compare`, `POST /auth/register|login`, `GET /auth/me`, `PATCH /experiments/{id}`, `GET|POST|DELETE /configs`, `POST|GET /reports`, `GET /reports/{id}/download`, `GET /exports/...`, `/investigations/...`; docs at `/api/docs`. Planned per spec: experiments (create, list,
get, run, clone, follow-up), models, fingerprints, failures, failure-clusters, reports.

## 8. Deployment architecture
Frontend, backend, database and inference are independent components, each replaceable.
- Local: `docker compose up --build` (nginx, FastAPI, PostgreSQL); optional local inference.
- Public demo: static/nginx frontend + container backend + hosted PostgreSQL + mock or small hosted model.
Free tiers change; `DEPLOYMENT.md` (Phase 8) will record the process as of its writing and make no permanence claims.

## 9. Security model
See [SECURITY.md](SECURITY.md): scrypt password hashing, HS256 JWT sessions, visibility enforced centrally for every endpoint,
per-IP and per-account abuse limits in public mode, production refuses a weak `SECRET_KEY`.

## 10. Milestones
Phases 1-9 as in the project brief. Done: Phase 1 (skeleton, schema, Docker, health), Phase 2 (adapters, engine, evaluators, first experiment), Phase 3 (statistics, metrics + evidence, charts, dashboard), Phase 4 (prompt mutation, anomaly detection, follow-ups, explain, lineage), Phase 5 (clustering, fingerprint, version comparison), Phase 6 (accounts, authorization, public-mode limits), Phase 7 (reports, exports, notebook, CLI).

## 11. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Free hosting changes or disappears | Provider-independent design; local Docker is the reference deployment. |
| Free CPUs too slow for real models publicly | Public mode limits experiment size; heavy runs are local. |
| LLM judges are biased | Deterministic evaluators first; judge output labelled and cross-checked. |
| Mock data mistaken for evidence | Mock banner, `is_demo_data` flag, reports refuse to present it as evidence. |
| Overclaiming causes | Evidence-level tagging built into the report generator. |
| Small samples | Every metric ships with n, interval and method. |
