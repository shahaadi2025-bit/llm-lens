# Definition of done: current status

Legend: **verified** = demonstrated by an automated test or a recorded run; **written, not run** = implemented but never run in
this environment; **not built**.

| Item | Status |
|---|---|
| Local Docker deployment (`docker compose up`) | written, not run (no Docker in the development environment) |
| Frontend / backend work | verified (tests, browser e2e, live server) |
| PostgreSQL | written, not run (migrations tested on SQLite; Neon connection string handling unit-tested; the deployed site has not been confirmed since early phases) |
| Mock mode without keys or GPU | verified |
| At least one real open model connected | **not verified**: adapters exist (Hugging Face, Ollama, OpenAI-compatible); none has run a real model |
| Model adapter, experiment engine, persistence | verified |
| Evaluators, statistics | verified (statistics checked against reference values) |
| Dashboard, behavioral fingerprint, comparison, lineage | verified (4 of 8 fingerprint dimensions measurable: M, S, I, C) |
| Anomaly detection, failure clustering, follow-up experiments | verified |
| Research notebook, reports, exports, CLI | verified (PDF export not built) |
| Responsive mobile UI | verified (screenshots and audit at 360/768/1024/1440 px) |
| Authentication, authorization, rate limiting | verified |
| Public deployment configuration | written (Render + Neon); an earlier version was deployed and answered health checks; the latest version's deployment is unconfirmed |
| Tests pass | verified: 230 backend (97% line coverage), 27 frontend, 9 browser steps |
| No secrets committed | verified by scanner; the project owner should also review their own repository |
| No fabricated results | verified by design: mock data is flagged `is_demo_data` and labelled everywhere; no real-model results exist |
| README, deployment docs, resume text | written |

## Not built
Four of the ten planned experiments (consistency, false premise, multilingual, tool use), so four of eight fingerprint
dimensions (reasoning, factuality, hallucination indicators, tool use) are empty; LLM-as-judge evaluation (the schema stores
judge details but no judge exists); PDF export; email verification and password reset; Redis-backed rate limiting.
