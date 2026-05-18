from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.api.pagination import Page
from app.deps import SessionDep, CurrentUserDep
from app.domains.mailing.filters import MailingFilter
from app.domains.mailing.services import MailingBatchingService
from .repositories import MailingRepository
from .schemas import MailingCreate, MailingRead

router = APIRouter(prefix="/mailings", tags=["mailings"])


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Health check endpoint."""
    return {"message": "pong"}


@router.get("/")
async def get_mailings(
    session: SessionDep,
    _current_user: CurrentUserDep,
    filters: Annotated[MailingFilter, Depends()],
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[MailingRead]:
    mailing_repository = MailingRepository(session)
    mailings = await mailing_repository.list(
        status=filters.status,
        limit=limit,
        offset=offset,
    )
    total = await mailing_repository.count(status=filters.status)
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[MailingRead.model_validate(mailing) for mailing in mailings],
    )


@router.post("/")
async def create_mailing(
    session: SessionDep,
    current_user: CurrentUserDep,
    payload: MailingCreate,
) -> MailingRead:
    mailing_repository = MailingRepository(session)
    mailing = await mailing_repository.create(payload, created_by_id=current_user.id)
    return MailingRead.model_validate(mailing)


@router.get("/{mailing_id}")
async def get_mailing(
    session: SessionDep,
    mailing_id: UUID,
    _current_user: CurrentUserDep,
) -> MailingRead:
    mailing_repository = MailingRepository(session)
    mailing = await mailing_repository.get_by_id(mailing_id)
    if mailing is None:
        raise HTTPException(status_code=404, detail="Mailing not found")

    return MailingRead.model_validate(mailing)


@router.delete("/{mailing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mailing(
    session: SessionDep,
    _current_user: CurrentUserDep,
    mailing_id: UUID,
) -> None:
    mailing_repository = MailingRepository(session)
    deleted = await mailing_repository.delete(mailing_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mailing not found")

    await session.commit()


@router.post("/{mailing_id}/send")
async def send_mailing(
    session: SessionDep,
    mailing_id: UUID,
    _current_user: CurrentUserDep,
) -> None:
    """Разбиваем на батчи -> prepared -> ставится в очередь паблишером"""
    mailing_repository = MailingRepository(session)
    mailing = await mailing_repository.get_by_id(mailing_id)
    if mailing is None:
        raise HTTPException(status_code=404, detail="Mailing not found")
        
    batching_service = MailingBatchingService(session)
    await batching_service.batch_mailing(mailing)
    return JSONResponse(status_code=200, content={"message": "Mailing batched"})