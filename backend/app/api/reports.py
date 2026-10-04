import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import optional_user, required_user
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models import Experiment, Investigation, Report, User
from app.reports.experiment_report import build_experiment_report
from app.reports.investigation_report import build_investigation_report
from app.schemas.reports import ReportCreate, ReportOut, ReportSummary
from app.services.access import can_see, get_visible, require_write_identity, visible
from app.services.exports import safe_filename

router = APIRouter(tags=["reports"])


def _summary(r: Report, user: User | None) -> ReportSummary:
    return ReportSummary(id=r.id, title=r.title, experiment_id=r.experiment_id, investigation_id=r.investigation_id,
                         includes_demo_data=r.includes_demo_data, owned_by_me=bool(user and r.owner_id == user.id),
                         created_at=r.created_at)


async def _readable(session: AsyncSession, r: Report, user: User | None) -> bool:
    """Owner always; otherwise only if the underlying experiment is visible to the viewer (so un-publishing hides it).
    Investigation reports are owner-only."""
    if user is not None and r.owner_id == user.id:
        return True
    if r.investigation_id is not None or r.experiment_id is None:
        return False
    exp = await session.get(Experiment, r.experiment_id)
    return exp is not None and can_see(exp, user)


async def _get(session: AsyncSession, report_id: uuid.UUID, user: User | None) -> Report:
    r = await session.get(Report, report_id)
    if r is None or not await _readable(session, r, user):
        raise HTTPException(404, "report not found")
    return r


@router.post("/reports", response_model=ReportOut, status_code=201)
async def create_report(body: ReportCreate, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings),
                        user: User | None = Depends(optional_user)) -> ReportOut:
    require_write_identity(user, settings)
    if settings.public_demo_mode:
        total = (await session.execute(select(func.count()).select_from(Report))).scalar_one()
        mine = (await session.execute(select(func.count()).select_from(Report).where(
            Report.owner_id == user.id))).scalar_one() if user else 0
        if total >= settings.public_max_reports or mine >= settings.public_max_reports_per_user:
            raise HTTPException(429, "The public demo has reached its report limit.")
    if body.experiment_id is not None:
        exp = await get_visible(session, body.experiment_id, user)
        title, content, demo = await build_experiment_report(session, exp)
        r = Report(owner_id=user.id if user else None, experiment_id=exp.id, title=body.title or title, content=content,
                   includes_demo_data=demo)
    else:
        if user is None:
            raise HTTPException(401, "sign in required", headers={"WWW-Authenticate": "Bearer"})
        inv = await session.get(Investigation, body.investigation_id)
        if inv is None or inv.owner_id != user.id:
            raise HTTPException(404, "investigation not found")
        title, content, demo = await build_investigation_report(session, inv, user)
        r = Report(owner_id=user.id, investigation_id=inv.id, title=body.title or title, content=content, includes_demo_data=demo)
    session.add(r)
    await session.commit()
    return ReportOut(**_summary(r, user).model_dump(), content=r.content)


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports(session: AsyncSession = Depends(get_session), user: User | None = Depends(optional_user),
                       limit: int = Query(default=50, ge=1, le=200)) -> list[ReportSummary]:
    cond: list[ColumnElement[bool]] = [Report.experiment_id.in_(select(Experiment.id).where(visible(user)))]
    if user is not None:
        cond.append(Report.owner_id == user.id)
    rows = (await session.execute(select(Report).where(or_(*cond)).order_by(Report.created_at.desc()).limit(limit))).scalars()
    return [_summary(r, user) for r in rows if r.investigation_id is None or (user and r.owner_id == user.id)]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(report_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                     user: User | None = Depends(optional_user)) -> ReportOut:
    r = await _get(session, report_id, user)
    return ReportOut(**_summary(r, user).model_dump(), content=r.content)


@router.get("/reports/{report_id}/download")
async def download_report(report_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                          user: User | None = Depends(optional_user)) -> Response:
    r = await _get(session, report_id, user)
    return Response(r.content, media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{safe_filename(r.title, "md")}"', "X-Content-Type-Options": "nosniff"})


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(report_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                        user: User = Depends(required_user)) -> None:
    r = await session.get(Report, report_id)
    if r is None or r.owner_id != user.id:
        raise HTTPException(404, "report not found")
    await session.delete(r)
    await session.commit()
