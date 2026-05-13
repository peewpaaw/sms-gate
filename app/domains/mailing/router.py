from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.pagination import Page
from app.deps import SessionDep, CurrentUserDep
from app.domains.mailing.filters import MailingFilter
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