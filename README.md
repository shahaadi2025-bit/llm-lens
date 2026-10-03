# LLM Lens
**Black-Box LLM Behavioral Intelligence Platform**

Run controlled experiments on language models treated as black boxes, then trace every metric back to
the prompts, responses and evaluators behind it.

> **Status: Phase 6 of 9.** Working: model adapters (mock, local Hugging Face, Ollama, OpenAI-compatible), experiment
> engine, deterministic evaluators, statistics, metrics with evidence traceability, prompt mutations, anomaly detection,
> controlled follow-ups, "Explain this failure", lineage, failure clustering, behavioral fingerprint, matched-design
> version comparison, accounts (scrypt + JWT), private/public experiments enforced on every endpoint, saved configurations,
> public-demo limits (rate, quota, concurrency), charts, dashboard and free-hosting config.
> Not built yet: reports, CLI, export, research notebook, remaining experiment types (6 of 8 fingerprint dimensions are empty).
> The local Hugging Face adapter is written but has not been run against a real model yet. See [docs/SECURITY.md](docs/SECURITY.md).

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
[Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md). Deployment, experiments, evaluation and reproducibility docs arrive in later phases.

## License
MIT
