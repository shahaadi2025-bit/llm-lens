import json

import httpx
import pytest

from app.core.config import Settings
from app.core.hardware import DeviceError, detect_hardware, resolve_device
from app.services.adapters.base import AdapterError, GenerationRequest
from app.services.adapters.factory import build_adapter
from app.services.adapters.http_adapters import OllamaAdapter, OpenAICompatAdapter
from app.services.adapters.mock import MockAdapter


async def test_mock_is_deterministic_and_labelled():
    a = MockAdapter()
    req = GenerationRequest(prompt="What is 37 × 84?", seed=3)
    r1, r2 = await a.generate(req), await a.generate(req)
    assert r1.text == r2.text
    assert r1.raw["mock"] is True
    assert a.get_model_info().is_mock


async def test_mock_gets_some_but_not_all_products_wrong():
    a = MockAdapter()
    outs = [(await a.generate(GenerationRequest(prompt=f"What is {x} × {x + 7}?"))).text for x in range(12, 112)]
    correct = sum(f"is {x * (x + 7)}." in o for x, o in zip(range(12, 112), outs, strict=True))
    assert 60 < correct < 100  # ~85% correct by construction; both outcomes are exercised


async def test_mock_handles_all_representations():
    a = MockAdapter()
    for p in ["12 * 12 = ?", "12 groups of 12?", "12 × 12"]:
        assert (await a.generate(GenerationRequest(prompt=p, seed=1))).text.startswith("The answer is ")
    assert "[MOCK]" in (await a.generate(GenerationRequest(prompt="hello"))).text


def test_estimate_tokens():
    a = MockAdapter()
    assert a.estimate_tokens("") == 0
    assert a.estimate_tokens("abcdefgh") == 2


async def test_stream_default_yields_full_text():
    chunks = [c async for c in MockAdapter().stream(GenerationRequest(prompt="hi"))]
    assert chunks == ["[MOCK] No real model was run for this prompt."]


async def test_ollama_adapter_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["options"]["seed"] == 7 and body["stream"] is False
        return httpx.Response(200, json={"response": "42", "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2})

    a = OllamaAdapter("http://x", "m", transport=httpx.MockTransport(handler))
    r = await a.generate(GenerationRequest(prompt="q", seed=7))
    assert (r.text, r.prompt_tokens, r.completion_tokens) == ("42", 5, 2)
    assert a.get_model_info().provider == "ollama"


async def test_openai_compat_adapter_parses_and_sends_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 1}})

    a = OpenAICompatAdapter("http://x", "m", api_key="k", transport=httpx.MockTransport(handler))
    r = await a.generate(GenerationRequest(prompt="q", system="s"))
    assert r.text == "ok" and r.completion_tokens == 1


async def test_http_adapters_wrap_errors():
    a = OllamaAdapter("http://x", "m", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(AdapterError):
        await a.generate(GenerationRequest(prompt="q"))
    b = OpenAICompatAdapter("http://x", "m", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"x": 1})))
    with pytest.raises(AdapterError, match="choices"):
        await b.generate(GenerationRequest(prompt="q"))


def test_factory_selects_provider_and_validates():
    assert isinstance(build_adapter(Settings(model_provider="mock")), MockAdapter)
    assert isinstance(build_adapter(Settings(model_provider="ollama", model_name="qwen")), OllamaAdapter)
    with pytest.raises(AdapterError):
        build_adapter(Settings(model_provider="openai_compatible"))


def test_hardware_detection_and_device_resolution():
    hw = detect_hardware()
    assert hw["recommended_device"] in ("cpu", "cuda")
    assert resolve_device("auto") == hw["recommended_device"]
    if not hw["cuda_available"]:
        with pytest.raises(DeviceError):
            resolve_device("cuda")
