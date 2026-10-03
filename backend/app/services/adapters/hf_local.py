"""Local Hugging Face adapter. torch/transformers are imported lazily so mock mode needs neither.

Models are never downloaded automatically at import time: the first generate() call loads MODEL_NAME.
"""
import asyncio
import threading
import time
from typing import Any

from app.core.hardware import resolve_device
from app.services.adapters.base import AdapterError, GenerationRequest, GenerationResult, ModelAdapter, ModelInfo


class HuggingFaceAdapter(ModelAdapter):
    def __init__(self, model_name: str, device: str = "auto", context_length: int = 4096,
                 revision: str | None = None) -> None:
        self._name = model_name
        self._device_pref = device
        self._ctx = context_length
        self._revision = revision
        self._model: Any = None
        self._tokenizer: Any = None
        self._device = "cpu"
        self._lock = threading.Lock()  # one generation at a time per loaded model

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(slug=f"hf/{self._name}", display_name=self._name, provider="local",
                         context_length=self._ctx, revision=self._revision,
                         version_label=self._revision or "main", capabilities={"streaming": False})

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415
        except ImportError as exc:
            raise AdapterError("Local models need torch + transformers: pip install -r requirements-ml.txt") from exc
        self._device = resolve_device(self._device_pref)
        self._tokenizer = AutoTokenizer.from_pretrained(self._name, revision=self._revision)
        self._model = AutoModelForCausalLM.from_pretrained(self._name, revision=self._revision).to(self._device)
        self._model.eval()

    def _generate_sync(self, req: GenerationRequest) -> GenerationResult:
        import torch  # noqa: PLC0415

        with self._lock:
            self._load()
            tok = self._tokenizer
            if getattr(tok, "chat_template", None):
                msgs = ([{"role": "system", "content": req.system}] if req.system else []) + [
                    {"role": "user", "content": req.prompt}]
                text_in = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            else:
                text_in = (req.system + "\n\n" if req.system else "") + req.prompt
            inputs = tok(text_in, return_tensors="pt").to(self._device)
            torch.manual_seed(req.seed)
            sample = req.temperature > 0
            kwargs: dict[str, Any] = {"max_new_tokens": req.max_tokens, "do_sample": sample,
                                      "pad_token_id": tok.pad_token_id or tok.eos_token_id}
            if sample:
                kwargs["temperature"] = req.temperature
            start = time.perf_counter()
            with torch.no_grad():
                out = self._model.generate(**inputs, **kwargs)
            new_tokens = out[0][inputs["input_ids"].shape[1]:]
            return GenerationResult(
                text=tok.decode(new_tokens, skip_special_tokens=True),
                finish_reason="stop" if len(new_tokens) < req.max_tokens else "length",
                prompt_tokens=int(inputs["input_ids"].shape[1]), completion_tokens=int(len(new_tokens)),
                raw={"device": self._device, "gen_seconds": round(time.perf_counter() - start, 3)},
            )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return await asyncio.to_thread(self._generate_sync, request)
