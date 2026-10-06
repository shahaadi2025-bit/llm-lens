"""The Hugging Face adapter's own logic (templating, sampling arguments, token accounting, loading, error paths), tested with
small stand-ins for torch/transformers. This does NOT prove a real model works: it proves the adapter calls the library
correctly. A real-model run is still required before claiming real results."""
import contextlib
import sys
import types

import pytest

from app.core.hardware import DeviceError
from app.services.adapters.base import AdapterError, GenerationRequest
from app.services.adapters.factory import build_adapter
from app.services.adapters.hf_local import HuggingFaceAdapter


class Seq(list):
    @property
    def shape(self):
        return (len(self),)


class Batch(dict):
    def to(self, _device):
        return self


class FakeTokenizer:
    pad_token_id = None
    eos_token_id = 7

    def __init__(self, template):
        self.chat_template = template
        self.seen_text = None
        self.seen_messages = None

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        self.seen_messages = messages
        return "|".join(f"{m['role']}:{m['content']}" for m in messages) + "|assistant:"

    def __call__(self, text, return_tensors):
        self.seen_text = text
        ids = Seq(range(len(text.split())))
        return Batch(input_ids=types.SimpleNamespace(shape=(1, len(ids))))

    def decode(self, tokens, skip_special_tokens):
        return "decoded:" + ",".join(str(t) for t in tokens)


class FakeModel:
    def __init__(self, n_new):
        self.n_new = n_new
        self.kwargs = None

    def to(self, _device):
        return self

    def eval(self):
        pass

    def generate(self, **kwargs):
        self.kwargs = kwargs
        prompt_len = kwargs["input_ids"].shape[1]
        return [list(range(prompt_len)) + list(range(100, 100 + self.n_new))]


@pytest.fixture
def stubs(monkeypatch):
    state = types.SimpleNamespace(seed=None, loads=0, tok=FakeTokenizer("tmpl"), model=FakeModel(3))
    torch = types.ModuleType("torch")
    torch.manual_seed = lambda s: setattr(state, "seed", s)
    torch.no_grad = lambda: contextlib.nullcontext()
    tf = types.ModuleType("transformers")

    def tok_from(*_a, **_k):
        state.loads += 1
        return state.tok

    tf.AutoTokenizer = types.SimpleNamespace(from_pretrained=tok_from)
    tf.AutoModelForCausalLM = types.SimpleNamespace(from_pretrained=lambda *_a, **_k: state.model)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", tf)
    monkeypatch.setattr("app.services.adapters.hf_local.resolve_device", lambda pref: "cpu")
    return state


async def test_chat_template_greedy_decoding_and_token_accounting(stubs):
    a = HuggingFaceAdapter("org/model", revision="abc123")
    r = await a.generate(GenerationRequest(prompt="What is 2+2?", system="Be brief.", temperature=0.0, max_tokens=16, seed=9))
    assert stubs.tok.seen_messages == [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "What is 2+2?"}]
    kw = stubs.model.kwargs
    assert kw["do_sample"] is False and "temperature" not in kw and kw["max_new_tokens"] == 16 and kw["pad_token_id"] == 7
    assert stubs.seed == 9
    assert r.text == "decoded:100,101,102" and r.completion_tokens == 3 and r.prompt_tokens > 0
    assert r.finish_reason == "stop" and r.raw["device"] == "cpu"
    info = a.get_model_info()
    assert (info.slug, info.provider, info.revision, info.version_label) == ("hf/org/model", "local", "abc123", "abc123")


async def test_sampling_passes_temperature_and_length_finish_reason(stubs):
    stubs.model = FakeModel(4)
    r = await HuggingFaceAdapter("m").generate(GenerationRequest(prompt="hi", temperature=0.7, max_tokens=4))
    assert stubs.model.kwargs["do_sample"] is True and stubs.model.kwargs["temperature"] == 0.7
    assert r.finish_reason == "length"  # produced exactly max_tokens


async def test_plain_prompt_when_the_tokenizer_has_no_chat_template(stubs):
    stubs.tok = FakeTokenizer(None)
    await HuggingFaceAdapter("m").generate(GenerationRequest(prompt="question", system="sys"))
    assert stubs.tok.seen_text == "sys\n\nquestion"
    await HuggingFaceAdapter("m").generate(GenerationRequest(prompt="question"))
    assert stubs.tok.seen_text == "question"


async def test_model_is_loaded_once_and_reused(stubs):
    a = HuggingFaceAdapter("m")
    for _ in range(3):
        await a.generate(GenerationRequest(prompt="x"))
    assert stubs.loads == 1


async def test_missing_libraries_give_an_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))
    monkeypatch.setitem(sys.modules, "transformers", None)  # makes `import transformers` raise ImportError
    with pytest.raises(AdapterError, match="requirements-ml.txt"):
        await HuggingFaceAdapter("m").generate(GenerationRequest(prompt="x"))


def test_factory_builds_local_adapter_and_cuda_is_never_silently_downgraded(monkeypatch):
    from app.core.config import Settings

    a = build_adapter(Settings(model_provider="local", model_name="org/m", device="cuda"))
    assert isinstance(a, HuggingFaceAdapter)
    from app.core import hardware

    monkeypatch.setattr(hardware, "detect_hardware", lambda: {"cuda_available": False, "recommended_device": "cpu"})
    with pytest.raises(DeviceError):
        hardware.resolve_device("cuda")
    assert hardware.resolve_device("cpu") == "cpu" and hardware.resolve_device("auto") == "cpu"
