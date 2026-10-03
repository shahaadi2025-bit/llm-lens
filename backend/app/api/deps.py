from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.experiments.engine import ExperimentEngine, ModelUnavailable
from app.services.adapters.base import ModelAdapter
from app.services.adapters.factory import build_adapter
from app.services.adapters.mock import MOCK_MODELS, MockAdapter


@lru_cache
def get_adapter() -> ModelAdapter:
    return build_adapter(get_settings())


def adapter_provider(slug: str) -> ModelAdapter:
    adapter = get_adapter()
    if adapter.get_model_info().slug == slug:
        return adapter
    if get_settings().is_mock and slug in MOCK_MODELS:  # demo convenience: both mock versions are always runnable
        return MockAdapter(slug, get_settings().model_context_length)
    raise ModelUnavailable(f"model {slug!r} is not available on this server")


def available_adapters() -> list[ModelAdapter]:
    out = [get_adapter()]
    if get_settings().is_mock:
        out += [MockAdapter(s, get_settings().model_context_length) for s in MOCK_MODELS
                if s != out[0].get_model_info().slug]
    return out


@lru_cache
def get_engine() -> ExperimentEngine:
    s: Settings = get_settings()
    return ExperimentEngine(get_sessionmaker(), adapter_provider, max_concurrency=s.max_concurrency,
                            run_timeout_s=s.request_timeout_s, max_retries=s.max_retries,
                            retry_backoff_s=s.retry_backoff_s)
