from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUserDep, SessionDep
from app.models.mailing import Mailing
from app.models.sms_message import SmsMessage
from app.schemas.mailing import MailingCreate, MailingCreateResponse, MailingRead, SmsMessageRead
from app.services.idempotency import create_mailing_idempotently
from app.services.mailing import create_mailing, get_mailing_for_user

router = APIRouter(prefix="/sms/mailings", tags=["mailings"])


@router.post("", response_model=MailingCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_sms_mailing(
    payload: MailingCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> MailingCreateResponse:
    if idempotency_key:
        return await create_mailing_idempotently(
            session=session,
            current_user=current_user,
            payload=payload,
            key=idempotency_key,
            correlation_id=correlation_id,
        )
    return await create_mailing(session, current_user, payload, correlation_id=correlation_id)


@router.get("", response_model=list[MailingRead])
async def list_mailings(
    session: SessionDep,
    current_user: CurrentUserDep,
    provider_code: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[MailingRead]:
    stmt = (
        select(Mailing)
        .where(Mailing.created_by == current_user.id)
        .order_by(Mailing.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if provider_code:
        stmt = stmt.where(Mailing.provider_code == provider_code)
    mailings = (await session.scalars(stmt)).all()
    return [
        MailingRead(
            id=mailing.id,
            provider_code=mailing.provider_code,
            sender=mailing.sender,
            status=mailing.status,
            message_count=mailing.message_count,
        )
        for mailing in mailings
    ]


@router.get("/{mailing_id}", response_model=MailingRead)
async def get_mailing(
    mailing_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MailingRead:
    mailing = await get_mailing_for_user(session, mailing_id, current_user)
    if mailing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailing not found")
    return MailingRead(
        id=mailing.id,
        provider_code=mailing.provider_code,
        sender=mailing.sender,
        status=mailing.status,
        message_count=mailing.message_count,
    )


@router.get("/{mailing_id}/messages", response_model=list[SmsMessageRead])
async def list_mailing_messages(
    mailing_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[SmsMessageRead]:
    mailing = await session.scalar(
        select(Mailing)
        .where(Mailing.id == mailing_id, Mailing.created_by == current_user.id)
        .options(selectinload(Mailing.messages))
    )
    if mailing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailing not found")
    return [_message_read(message) for message in mailing.messages]


def _message_read(message: SmsMessage) -> SmsMessageRead:
    return SmsMessageRead(
        id=message.id,
        mailing_id=message.mailing_id,
        batch_id=message.batch_id,
        provider_code=message.provider_code,
        provider_custom_id=message.provider_custom_id,
        provider_message_id=message.provider_message_id,
        msisdn=message.msisdn,
        text=message.text,
        sender=message.sender,
        status=message.status,
        raw_provider_status=message.raw_provider_status,
    )
