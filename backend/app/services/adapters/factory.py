from app.core.config import Settings
from app.services.adapters.base import AdapterError, ModelAdapter
from app.services.adapters.hf_local import HuggingFaceAdapter
from app.services.adapters.http_adapters import OllamaAdapter, OpenAICompatAdapter
from app.services.adapters.mock import MockAdapter


def build_adapter(settings: Settings) -> ModelAdapter:
    provider, name, ctx = settings.model_provider, settings.model_name, settings.model_context_length
    if provider == "mock":
        return MockAdapter(name, ctx)
    if provider == "local":
        return HuggingFaceAdapter(name, settings.device, ctx)
    if provider == "ollama":
        return OllamaAdapter(settings.ollama_base_url, name, ctx, settings.request_timeout_s)
    if provider == "openai_compatible":
        if not settings.openai_compat_base_url:
            raise AdapterError("OPENAI_COMPAT_BASE_URL must be set for MODEL_PROVIDER=openai_compatible")
        key = settings.openai_compat_api_key.get_secret_value() if settings.openai_compat_api_key else None
        return OpenAICompatAdapter(settings.openai_compat_base_url, name, key, ctx, settings.request_timeout_s)
    raise AdapterError(f"unknown provider {provider!r}")
