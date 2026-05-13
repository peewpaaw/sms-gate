from fastapi import APIRouter, Query

from app.api.pagination import Page
from app.deps import SessionDep, CurrentUserDep
from app.domains.mailing.filters import MailingFilter
from .repositories import MailingRepository
from .schemas import MailingRead

router = APIRouter(prefix="/mailings", tags=["mailings"])


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Health check endpoint."""
    return {"message": "pong"}


@router.get("/")
async def get_mailings(
    session: SessionDep,
    _current_user: CurrentUserDep,
    filters: MailingFilter,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[MailingRead]:
    mailing_repository = MailingRepository(session)
    mailings = await mailing_repository.list(limit=limit, offset=offset)
    total = 0
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[MailingRead.model_validate(mailing) for mailing in mailings],
    )
