import json
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user
from app.core.db import get_session
from app.models import Experiment, User
from app.services.access import get_visible, visible
from app.services.exports import experiment_bundle, runs_csv, safe_filename, summary_csv

router = APIRouter(tags=["exports"])
NOSNIFF = {"X-Content-Type-Options": "nosniff"}


def _attach(name: str, ext: str) -> dict[str, str]:
    return {**NOSNIFF, "Content-Disposition": f'attachment; filename="{safe_filename(name, ext)}"'}


@router.get("/exports/experiments/{experiment_id}.json")
async def export_json(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                      user: User | None = Depends(optional_user)) -> Response:
    exp = await get_visible(session, experiment_id, user)
    return Response(json.dumps(await experiment_bundle(session, exp), indent=2, default=str), media_type="application/json",
                    headers=_attach(exp.name, "json"))


@router.get("/exports/experiments/{experiment_id}/runs.csv")
async def export_runs_csv(experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                          user: User | None = Depends(optional_user)) -> Response:
    exp = await get_visible(session, experiment_id, user)
    return Response(await runs_csv(session, exp), media_type="text/csv; charset=utf-8", headers=_attach(f"{exp.name}-runs", "csv"))


@router.get("/exports/experiments.csv")
async def export_summary_csv(session: AsyncSession = Depends(get_session), user: User | None = Depends(optional_user),
                             limit: int = Query(default=500, ge=1, le=2000)) -> Response:
    exps = list((await session.execute(select(Experiment).where(visible(user)).order_by(Experiment.created_at.desc())
                                       .limit(limit))).scalars())
    return Response(await summary_csv(session, exps), media_type="text/csv; charset=utf-8", headers=_attach("experiments", "csv"))
