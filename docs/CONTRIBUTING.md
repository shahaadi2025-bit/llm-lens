# Contributing

## Setup
```bash
pip install -r backend/requirements-dev.txt && pip install -e backend
cd frontend && npm install
```
Checks before a pull request: `cd backend && ruff check . && mypy app && pytest --cov=app`, `cd frontend && npx tsc -b --noEmit && npm test && npm run build`, `python scripts/scan_secrets.py`.

## Principles (non-negotiable)
1. **Deterministic first.** Use an LLM judge only where meaning genuinely needs one; label it, store judge model, prompt, version and criteria.
2. **Every number ships with n, interval and method**, and links to the runs behind it.
3. **Never state a cause or mechanism** a black-box experiment cannot observe. Evidence levels: observation, correlation, hypothesis, supported conclusion.
4. **Mock data is never evidence.** Anything from the mock model is flagged `is_demo_data` and labelled.
5. **Visibility is centralised** (`services/access.py`). Any new endpoint exposing experiment-derived data must filter through it, and needs a test as owner, stranger and anonymous.
6. **Reproducible by construction**: prompt generation is a pure function of configuration and seed.

## Add a model provider
Subclass `ModelAdapter` (`app/services/adapters/base.py`): `generate()`, `get_model_info()` (and optionally `stream()`, `estimate_tokens()`). Register it in `adapters/factory.py` and add its settings to `core/config.py` and `.env.example`. Test it against a simulated server (see `tests/test_adapters.py`, which uses `httpx.MockTransport`). Do not hard-code a provider anywhere else.

## Add an evaluator
```python
class ContainsMatch(Evaluator):
    name = "contains_match"
    def evaluate(self, response: str, expected: str | None) -> EvalResult: ...
```
Put it in `app/evaluators/`, register it in `registry.py`, record any extraction rule and known limitation in `details` and `docs/EVALUATION.md`, and test edge cases (empty response, missing expected value).

## Add an experiment type
Subclass `ExperimentType` (`app/experiments/types/base.py`): `task_type`, `title`, a documented `research_question`, `default_evaluator`, `validate_config()`, `build_items()` (deterministic), and optionally `group_of()` / `block_of()` (for form comparisons) and `fingerprint_dimension`. Register it in `experiments/registry.py`, add a template in `experiments/templates/`, document it in `docs/EXPERIMENTS.md`, and test determinism and invalid configuration.

## Migrations
`cd backend && alembic revision --autogenerate -m "message"`; use portable types (JSON, Uuid, VARCHAR); check `upgrade` and `downgrade` on SQLite.
