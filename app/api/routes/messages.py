from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models.mailing import Mailing
from app.models.sms_message import SmsMessage
from app.schemas.mailing import SmsMessageRead

router = APIRouter(prefix="/sms/messages", tags=["messages"])


@router.get("", response_model=list[SmsMessageRead])
async def list_messages(
    session: SessionDep,
    current_user: CurrentUserDep,
    provider_code: str | None = None,
    msisdn: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SmsMessageRead]:
    stmt = (
        select(SmsMessage)
        .join(Mailing, Mailing.id == SmsMessage.mailing_id)
        .where(Mailing.created_by == current_user.id)
        .order_by(SmsMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if provider_code:
        stmt = stmt.where(SmsMessage.provider_code == provider_code)
    if msisdn:
        stmt = stmt.where(SmsMessage.msisdn == msisdn)
    messages = (await session.scalars(stmt)).all()
    return [_message_read(message) for message in messages]


@router.get("/{message_id}", response_model=SmsMessageRead)
async def get_message(
    message_id: UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SmsMessageRead:
    message = await session.scalar(
        select(SmsMessage)
        .join(Mailing, Mailing.id == SmsMessage.mailing_id)
        .where(SmsMessage.id == message_id, Mailing.created_by == current_user.id)
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return _message_read(message)


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
