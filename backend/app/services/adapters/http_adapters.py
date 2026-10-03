"""HTTP-based adapters: Ollama (local, free) and any OpenAI-compatible endpoint (optional)."""
from typing import Any

import httpx

from app.services.adapters.base import AdapterError, GenerationRequest, GenerationResult, ModelAdapter, ModelInfo


async def _post(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise AdapterError(f"{type(exc).__name__}: {exc}") from exc
    except ValueError as exc:
        raise AdapterError("provider returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise AdapterError("provider returned unexpected payload")
    return data


class OllamaAdapter(ModelAdapter):
    def __init__(self, base_url: str, model_name: str, context_length: int = 4096, timeout_s: float = 60.0,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport)
        self._name = model_name
        self._ctx = context_length

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(slug=f"ollama/{self._name}", display_name=self._name, provider="ollama",
                         context_length=self._ctx, capabilities={"streaming": False})

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        payload: dict[str, Any] = {
            "model": self._name, "prompt": request.prompt, "stream": False,
            "options": {"temperature": request.temperature, "seed": request.seed, "num_predict": request.max_tokens},
        }
        if request.system:
            payload["system"] = request.system
        data = await _post(self._client, "/api/generate", payload)
        if "response" not in data:
            raise AdapterError("Ollama response missing 'response' field")
        return GenerationResult(
            text=str(data["response"]), finish_reason=data.get("done_reason"),
            prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"),
            raw={"model": data.get("model")},
        )


class OpenAICompatAdapter(ModelAdapter):
    def __init__(self, base_url: str, model_name: str, api_key: str | None = None, context_length: int = 4096,
                 timeout_s: float = 60.0, transport: httpx.AsyncBaseTransport | None = None) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_s, headers=headers,
                                         transport=transport)
        self._name = model_name
        self._ctx = context_length

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(slug=f"openai-compat/{self._name}", display_name=self._name, provider="openai_compatible",
                         context_length=self._ctx, capabilities={"streaming": False})

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        messages = ([{"role": "system", "content": request.system}] if request.system else []) + [
            {"role": "user", "content": request.prompt}]
        data = await _post(self._client, "/v1/chat/completions", {
            "model": self._name, "messages": messages, "temperature": request.temperature,
            "max_tokens": request.max_tokens, "seed": request.seed,
        })
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError("OpenAI-compatible response missing choices[0].message.content") from exc
        usage = data.get("usage") or {}
        return GenerationResult(text=text, finish_reason=choice.get("finish_reason"),
                                prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                                raw={"model": data.get("model")})
