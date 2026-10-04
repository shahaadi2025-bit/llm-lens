import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import required_user
from app.api.experiments import _summaries
from app.core.db import get_session
from app.models import Experiment, Investigation, InvestigationExperiment, InvestigationNote, User
from app.schemas.reports import (
    InvestigationCreate,
    InvestigationDetail,
    InvestigationSummary,
    InvestigationUpdate,
    LinkExperiment,
    NoteCreate,
    NoteOut,
)
from app.services.access import can_see

router = APIRouter(tags=["notebook"])
MAX_INVESTIGATIONS = 100
MAX_NOTES = 200


async def _own(session: AsyncSession, inv_id: uuid.UUID, user: User) -> Investigation:
    inv = await session.get(Investigation, inv_id)
    if inv is None or inv.owner_id != user.id:
        raise HTTPException(404, "investigation not found")  # someone else's notebook looks nonexistent
    return inv


async def _detail(session: AsyncSession, inv: Investigation, user: User) -> InvestigationDetail:
    ids = list((await session.execute(select(InvestigationExperiment.experiment_id).where(
        InvestigationExperiment.investigation_id == inv.id))).scalars())
    exps = [e for e in [await session.get(Experiment, i) for i in ids] if e is not None and can_see(e, user)]
    notes = list((await session.execute(select(InvestigationNote).where(InvestigationNote.investigation_id == inv.id)
                                        .order_by(InvestigationNote.created_at))).scalars())
    return InvestigationDetail(
        id=inv.id, title=inv.title, research_question=inv.research_question, hypothesis=inv.hypothesis,
        conclusion=inv.conclusion, limitations=inv.limitations, experiments=await _summaries(session, exps, user),
        hidden_experiments=len(ids) - len(exps), notes=[NoteOut(id=n.id, kind=n.kind, text=n.text, created_at=n.created_at) for n in notes],
        created_at=inv.created_at, updated_at=inv.updated_at)


@router.post("/investigations", response_model=InvestigationDetail, status_code=201)
async def create(body: InvestigationCreate, session: AsyncSession = Depends(get_session),
                 user: User = Depends(required_user)) -> InvestigationDetail:
    n = (await session.execute(select(func.count()).select_from(Investigation).where(Investigation.owner_id == user.id))).scalar_one()
    if n >= MAX_INVESTIGATIONS:
        raise HTTPException(429, f"At most {MAX_INVESTIGATIONS} investigations per account.")
    inv = Investigation(owner_id=user.id, title=body.title, research_question=body.research_question, hypothesis=body.hypothesis)
    session.add(inv)
    await session.commit()
    return await _detail(session, inv, user)


@router.get("/investigations", response_model=list[InvestigationSummary])
async def list_investigations(session: AsyncSession = Depends(get_session),
                              user: User = Depends(required_user)) -> list[InvestigationSummary]:
    out = []
    for inv in (await session.execute(select(Investigation).where(Investigation.owner_id == user.id)
                                      .order_by(Investigation.updated_at.desc()))).scalars():
        ne = (await session.execute(select(func.count()).select_from(InvestigationExperiment)
                                    .where(InvestigationExperiment.investigation_id == inv.id))).scalar_one()
        nn = (await session.execute(select(func.count()).select_from(InvestigationNote)
                                    .where(InvestigationNote.investigation_id == inv.id))).scalar_one()
        out.append(InvestigationSummary(id=inv.id, title=inv.title, research_question=inv.research_question, n_experiments=ne,
                                        n_notes=nn, has_conclusion=bool(inv.conclusion.strip()), updated_at=inv.updated_at))
    return out


@router.get("/investigations/{inv_id}", response_model=InvestigationDetail)
async def get_investigation(inv_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                            user: User = Depends(required_user)) -> InvestigationDetail:
    return await _detail(session, await _own(session, inv_id, user), user)


@router.patch("/investigations/{inv_id}", response_model=InvestigationDetail)
async def update(inv_id: uuid.UUID, body: InvestigationUpdate, session: AsyncSession = Depends(get_session),
                 user: User = Depends(required_user)) -> InvestigationDetail:
    inv = await _own(session, inv_id, user)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            setattr(inv, k, v)
    # Scientific guard: a conclusion must travel with the limitations that qualify it.
    if inv.conclusion.strip() and not inv.limitations.strip():
        raise HTTPException(422, "State the limitations before recording a conclusion.")
    await session.commit()
    return await _detail(session, inv, user)


@router.delete("/investigations/{inv_id}", status_code=204)
async def remove_investigation(inv_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                               user: User = Depends(required_user)) -> None:
    inv = await _own(session, inv_id, user)
    await session.execute(delete(InvestigationNote).where(InvestigationNote.investigation_id == inv.id))
    await session.execute(delete(InvestigationExperiment).where(
        InvestigationExperiment.investigation_id == inv.id))
    await session.delete(inv)
    await session.commit()


@router.post("/investigations/{inv_id}/experiments", response_model=InvestigationDetail)
async def link_experiment(inv_id: uuid.UUID, body: LinkExperiment, session: AsyncSession = Depends(get_session),
                          user: User = Depends(required_user)) -> InvestigationDetail:
    inv = await _own(session, inv_id, user)
    exp = await session.get(Experiment, body.experiment_id)
    if exp is None or not can_see(exp, user):
        raise HTTPException(404, "experiment not found")
    if await session.get(InvestigationExperiment, (inv.id, exp.id)) is None:
        session.add(InvestigationExperiment(investigation_id=inv.id, experiment_id=exp.id))
        await session.commit()
    return await _detail(session, inv, user)


@router.delete("/investigations/{inv_id}/experiments/{experiment_id}", response_model=InvestigationDetail)
async def unlink_experiment(inv_id: uuid.UUID, experiment_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                            user: User = Depends(required_user)) -> InvestigationDetail:
    inv = await _own(session, inv_id, user)
    await session.execute(delete(InvestigationExperiment).where(
        InvestigationExperiment.investigation_id == inv.id, InvestigationExperiment.experiment_id == experiment_id))
    await session.commit()
    return await _detail(session, inv, user)


@router.post("/investigations/{inv_id}/notes", response_model=InvestigationDetail, status_code=201)
async def add_note(inv_id: uuid.UUID, body: NoteCreate, session: AsyncSession = Depends(get_session),
                   user: User = Depends(required_user)) -> InvestigationDetail:
    inv = await _own(session, inv_id, user)
    n = (await session.execute(select(func.count()).select_from(InvestigationNote)
                               .where(InvestigationNote.investigation_id == inv.id))).scalar_one()
    if n >= MAX_NOTES:
        raise HTTPException(429, f"At most {MAX_NOTES} notes per investigation.")
    session.add(InvestigationNote(investigation_id=inv.id, kind=body.kind, text=body.text))
    await session.commit()
    return await _detail(session, inv, user)


@router.delete("/investigations/{inv_id}/notes/{note_id}", response_model=InvestigationDetail)
async def delete_note(inv_id: uuid.UUID, note_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                      user: User = Depends(required_user)) -> InvestigationDetail:
    inv = await _own(session, inv_id, user)
    await session.execute(delete(InvestigationNote).where(
        InvestigationNote.id == note_id, InvestigationNote.investigation_id == inv.id))
    await session.commit()
    return await _detail(session, inv, user)
