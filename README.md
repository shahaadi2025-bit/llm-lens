# LLM Lens
**Black-Box LLM Behavioral Intelligence Platform**

Run controlled experiments on language models treated as black boxes, then trace every metric back to
the prompts, responses and evaluators behind it.

> **Status: Phase 4 of 9.** Working: model adapters (mock, local Hugging Face, Ollama, OpenAI-compatible), experiment
> engine (retry, timeout, cancel, resume), deterministic evaluators, statistics (Wilson/bootstrap intervals, effect sizes,
> Cochran's Q), metrics with evidence traceability, deterministic prompt mutations, a prompt-sensitivity experiment,
> anomaly detection (paired discordance, IQR, z-score, Isolation Forest), automated controlled follow-up experiments with a
> documented reproduction rule, "Explain this failure", experiment lineage, charts, dashboard and free public-hosting config.
> Not built yet: failure clustering, behavioral fingerprints, model comparison, auth, reports, CLI, notebook.
> The local Hugging Face adapter is written but has not been run against a real model yet.

## Quick start (local)
```bash
cp .env.example .env        # set POSTGRES_PASSWORD and SECRET_KEY
docker compose up --build   # then open http://localhost
```
Without Docker:
```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
DATABASE_URL=sqlite+aiosqlite:///./lens-dev.sqlite alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:///./lens-dev.sqlite uvicorn app.main:app --reload
# frontend (second terminal)
cd frontend && npm install && npm run dev      # http://localhost:5173
```
Tests: `cd backend && pytest` and `cd frontend && npm test`.

## Public deployment (free tiers)
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): one Docker service on Render + Neon PostgreSQL, using `render.yaml`.
The public demo runs the mock model only; it is clearly labelled and is not evidence about any real LLM.

## Docs
[Architecture](docs/ARCHITECTURE.md). Deployment, experiments, evaluation and reproducibility docs arrive in later phases.

## License
MIT
