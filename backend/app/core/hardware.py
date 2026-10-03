"""Hardware detection. Never imports torch unless it is installed (keeps mock/public mode light)."""
import importlib.util
import os
import platform
import sys
from typing import Any


class DeviceError(ValueError):
    pass


def _torch_info() -> dict[str, Any]:
    if importlib.util.find_spec("torch") is None:
        return {"torch_installed": False, "torch_version": None, "cuda_available": False, "cuda_device": None}
    import torch  # noqa: PLC0415 - deliberate lazy import

    cuda = bool(torch.cuda.is_available())
    return {
        "torch_installed": True,
        "torch_version": torch.__version__,
        "cuda_available": cuda,
        "cuda_device": torch.cuda.get_device_name(0) if cuda else None,
    }


def detect_hardware() -> dict[str, Any]:
    info = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        **_torch_info(),
    }
    info["recommended_device"] = "cuda" if info["cuda_available"] else "cpu"
    return info


def resolve_device(preference: str) -> str:
    """'auto' picks CUDA when available, else CPU. Asking for CUDA without it is an error, not a silent fallback."""
    hw = detect_hardware()
    if preference == "auto":
        return str(hw["recommended_device"])
    if preference == "cuda" and not hw["cuda_available"]:
        raise DeviceError("DEVICE=cuda requested but no CUDA GPU is available; use DEVICE=auto or cpu.")
    return preference
