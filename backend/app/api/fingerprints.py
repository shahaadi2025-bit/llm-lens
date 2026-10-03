import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import LLMModel
from app.schemas.fingerprint import CompareOut, FingerprintOut
from app.services.compare import compare_versions
from app.services.fingerprint import build_fingerprint

router = APIRouter(tags=["fingerprints"])


@router.get("/fingerprints/{model_id}", response_model=FingerprintOut)
async def fingerprint(model_id: uuid.UUID, version_id: uuid.UUID | None = None,
                      session: AsyncSession = Depends(get_session)) -> FingerprintOut:
    model = await session.get(LLMModel, model_id)
    if model is None:
        raise HTTPException(404, "model not found")
    return await build_fingerprint(session, model, version_id)


@router.get("/compare", response_model=CompareOut)
async def compare(a: uuid.UUID, b: uuid.UUID, session: AsyncSession = Depends(get_session)) -> CompareOut:
    if a == b:
        raise HTTPException(422, "choose two different model versions")
    try:
        return await compare_versions(session, a, b)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
