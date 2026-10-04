"""Load experiment templates (YAML). safe_load only: templates may come from anyone."""
from pathlib import Path
from typing import Any

import yaml

ALLOWED = {"name", "task_type", "research_question", "hypothesis", "model", "seed", "repetitions", "temperature", "max_tokens",
           "evaluator", "config", "is_public"}


class TemplateError(ValueError):
    pass


def load_template(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise TemplateError(f"template not found: {path}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TemplateError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TemplateError("a template must be a YAML mapping of settings")
    unknown = sorted(set(data) - ALLOWED)
    if unknown:
        raise TemplateError(f"unknown template keys: {unknown}; allowed: {sorted(ALLOWED)}")
    for required in ("name", "task_type"):
        if not isinstance(data.get(required), str) or not data[required].strip():
            raise TemplateError(f"template needs a non-empty '{required}'")
    if "config" in data and not isinstance(data["config"], dict):
        raise TemplateError("'config' must be a mapping")
    body = {k: v for k, v in data.items() if k != "model"}
    if data.get("model"):
        body["model_slug"] = str(data["model"])
    return body
