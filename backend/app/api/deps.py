from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.experiments.engine import ExperimentEngine, ModelUnavailable
from app.services.adapters.base import ModelAdapter
from app.services.adapters.factory import build_adapter


@lru_cache
def get_adapter() -> ModelAdapter:
    return build_adapter(get_settings())


def adapter_provider(slug: str) -> ModelAdapter:
    adapter = get_adapter()
    if adapter.get_model_info().slug != slug:
        raise ModelUnavailable(f"model {slug!r} is not the model this server is configured to run")
    return adapter


@lru_cache
def get_engine() -> ExperimentEngine:
    s: Settings = get_settings()
    return ExperimentEngine(get_sessionmaker(), adapter_provider, max_concurrency=s.max_concurrency,
                            run_timeout_s=s.request_timeout_s, max_retries=s.max_retries,
                            retry_backoff_s=s.retry_backoff_s)
