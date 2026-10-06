"""Creating, cloning and describing experiments (everything except executing them)."""
import hashlib
import importlib.metadata as md
import json
import platform
import sys
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_VERSION, Settings
from app.core.hardware import detect_hardware
from app.evaluators.registry import get_evaluator
from app.experiments.registry import get_experiment_type
from app.experiments.types.base import ConfigError
from app.models import Experiment, ExperimentLineage, ExperimentRun, LLMModel, ModelVersion, Prompt
from app.schemas.experiment import ExperimentCreate
from app.services.adapters.base import ModelInfo


class ServiceError(Exception):
    status_code = 400


class DuplicateExperiment(ServiceError):
    status_code = 409

    def __init__(self, existing_id: uuid.UUID) -> None:
        super().__init__(f"An identical experiment already exists ({existing_id}). Clone it to rerun on purpose.")
        self.existing_id = existing_id


class TooLarge(ServiceError):
    status_code = 422


async def ensure_model_version(session: AsyncSession, info: ModelInfo) -> ModelVersion:
    model = (await session.execute(select(LLMModel).where(LLMModel.slug == info.slug))).scalar_one_or_none()
    if model is None:
        model = LLMModel(slug=info.slug, display_name=info.display_name, provider=info.provider,
                         context_length=info.context_length, capabilities=info.capabilities, is_mock=info.is_mock)
        session.add(model)
        await session.flush()
    mv = (await session.execute(select(ModelVersion).where(
        ModelVersion.model_id == model.id, ModelVersion.version_label == info.version_label))).scalar_one_or_none()
    if mv is None:
        mv = ModelVersion(model_id=model.id, version_label=info.version_label, revision=info.revision)
        session.add(mv)
        await session.flush()
    return mv


def capture_environment(info: ModelInfo) -> dict[str, Any]:
    libs = {}
    for lib in ("fastapi", "sqlalchemy", "numpy", "scipy", "torch", "transformers"):
        try:
            libs[lib] = md.version(lib)
        except md.PackageNotFoundError:
            pass
    return {
        "python": sys.version.split()[0], "platform": platform.platform(), "libraries": libs,
        "hardware": detect_hardware(), "provider": info.provider, "model_revision": info.revision,
        "context_length": info.context_length,
    }


def _spec_hash(parts: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


async def create_experiment(
    session: AsyncSession, spec: ExperimentCreate, mv: ModelVersion, info: ModelInfo, settings: Settings,
    *, owner_id: uuid.UUID | None = None, allow_duplicate: bool = False,
) -> Experiment:
    try:
        etype = get_experiment_type(spec.task_type)
    except KeyError as exc:
        raise ServiceError(str(exc)) from exc
    evaluator_name = spec.evaluator or etype.default_evaluator
    try:
        get_evaluator(evaluator_name)
        config = etype.validate_config(spec.config)
        etype.validate_for_model(config, info.context_length)
        items = etype.build_items(config, spec.seed)
    except (KeyError, ConfigError) as exc:
        raise ServiceError(str(exc)) from exc

    total = len(items) * spec.repetitions
    chars = sum(len(i.prompt) for i in items) * spec.repetitions
    if chars > settings.effective_max_prompt_chars:
        raise TooLarge(f"{chars:,} prompt characters exceeds the limit of {settings.effective_max_prompt_chars:,} for this deployment.")
    if total > settings.effective_max_runs:
        raise TooLarge(f"{total} runs exceeds the limit of {settings.effective_max_runs} for this deployment.")

    spec_hash = _spec_hash({
        "task_type": spec.task_type, "model": info.slug, "version": info.version_label, "config": config,
        "seed": spec.seed, "temperature": spec.temperature, "max_tokens": spec.max_tokens,
        "repetitions": spec.repetitions, "evaluator": evaluator_name,
    })
    if not allow_duplicate:
        existing = (await session.execute(select(Experiment.id).where(
            Experiment.spec_hash == spec_hash, Experiment.owner_id == owner_id))).first()
        if existing:
            raise DuplicateExperiment(existing[0])

    exp = Experiment(
        owner_id=owner_id, model_version_id=mv.id, name=spec.name,
        research_question=spec.research_question or etype.research_question, hypothesis=spec.hypothesis,
        task_type=spec.task_type, temperature=spec.temperature, max_tokens=spec.max_tokens, seed=spec.seed,
        repetitions=spec.repetitions, evaluator=evaluator_name, config=config, spec_hash=spec_hash,
        software_version=APP_VERSION, environment=capture_environment(info), is_public=spec.is_public,
        is_demo_data=info.is_mock, context_length=info.context_length,
    )
    session.add(exp)
    await session.flush()

    run_index = 0
    for rep in range(spec.repetitions):
        for item in items:
            run = ExperimentRun(experiment_id=exp.id, run_index=run_index, variant_label=item.variant_label,
                                seed=spec.seed + rep)
            session.add(run)
            await session.flush()
            session.add(Prompt(
                run_id=run.id, text=item.prompt, system_text=item.system, variant_kind=item.variant_kind,
                variant_params={**item.variant_params, "repetition": rep}, expected_answer=item.expected,
                content_hash=hashlib.sha256(f"{item.system or ''}\n{item.prompt}".encode()).hexdigest()))
            run_index += 1
    await session.commit()
    return exp


async def clone_experiment(session: AsyncSession, original: Experiment, info: ModelInfo, settings: Settings,
                           mv: ModelVersion, owner_id: uuid.UUID | None = None) -> Experiment:
    spec = ExperimentCreate(
        name=f"{original.name} (clone)", research_question=original.research_question,
        hypothesis=original.hypothesis, task_type=original.task_type, temperature=original.temperature,
        max_tokens=original.max_tokens, seed=original.seed, repetitions=original.repetitions,
        evaluator=original.evaluator, config=original.config,
        is_public=False)  # a clone never inherits visibility: it belongs to whoever cloned it, private by default
    clone = await create_experiment(session, spec, mv, info, settings, owner_id=owner_id, allow_duplicate=True)
    session.add(ExperimentLineage(parent_experiment_id=original.id, child_experiment_id=clone.id, relation="clone"))
    await session.commit()
    return clone
