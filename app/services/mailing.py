from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.messaging.publisher import publish_send_batch
from app.messaging.schemas import SendBatchTask
from app.models.enums import (
    MailingSource,
    MailingStatus,
    SmsBatchStatus,
    SmsMessageStatus,
    UserRole,
)
from app.models.mailing import Mailing
from app.models.provider import Provider
from app.models.sms_batch import SmsBatch
from app.models.sms_message import SmsMessage
from app.models.user import User
from app.providers.registry import provider_registry
from app.schemas.mailing import MailingCreate, MailingCreateResponse, SmsMessageShort
from app.services.seeding import ensure_fake_provider


def generate_provider_custom_id() -> str:
    return f"msg_{uuid4().hex[:16]}"


async def get_active_provider(session: AsyncSession, provider_code: str) -> Provider:
    if provider_code == "auto":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="provider_code='auto' is reserved but unsupported in MVP",
        )

    if provider_code == "fake":
        await ensure_fake_provider(session)

    provider = await session.scalar(
        select(Provider).where(Provider.code == provider_code, Provider.is_active.is_(True))
    )
    if provider is None or not provider_registry.has(provider_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Provider {provider_code!r} is not supported",
        )
    return provider


async def create_mailing(
    session: AsyncSession,
    current_user: User,
    payload: MailingCreate,
    correlation_id: str | None = None,
    publish: bool = True,
    commit: bool = True,
) -> MailingCreateResponse:
    provider = await get_active_provider(session, payload.provider_code)
    source = MailingSource.ERP if current_user.role == UserRole.ERP else MailingSource.UI

    mailing = Mailing(
        created_by=current_user.id,
        source=source,
        provider_code=provider.code,
        sender=payload.sender,
        status=MailingStatus.QUEUED,
        message_count=len(payload.messages),
    )
    session.add(mailing)
    await session.flush()

    batches: list[SmsBatch] = []
    messages: list[SmsMessage] = []
    for offset in range(0, len(payload.messages), provider.max_batch_size):
        chunk = payload.messages[offset : offset + provider.max_batch_size]
        batch = SmsBatch(
            mailing_id=mailing.id,
            provider_code=provider.code,
            status=SmsBatchStatus.QUEUED,
            message_count=len(chunk),
        )
        session.add(batch)
        await session.flush()
        batches.append(batch)

        for item in chunk:
            message = SmsMessage(
                mailing_id=mailing.id,
                batch_id=batch.id,
                provider_code=provider.code,
                provider_custom_id=generate_provider_custom_id(),
                msisdn=item.msisdn,
                text=item.text,
                sender=payload.sender,
                status=SmsMessageStatus.QUEUED,
            )
            session.add(message)
            messages.append(message)

    await session.flush()

    response = MailingCreateResponse(
        mailing_id=mailing.id,
        status=mailing.status,
        messages=[
            SmsMessageShort(message_id=message.id, status=message.status) for message in messages
        ],
    )

    if commit:
        await session.commit()

    if publish and commit:
        for batch_id in [batch.id for batch in batches]:
            await publish_send_batch(
                SendBatchTask(
                    batch_id=batch_id,
                    mailing_id=mailing.id,
                    provider_code=provider.code,
                    correlation_id=correlation_id,
                )
            )

    return response


async def get_mailing_for_user(
    session: AsyncSession, mailing_id: UUID, current_user: User
) -> Mailing | None:
    return await session.scalar(
        select(Mailing)
        .where(Mailing.id == mailing_id, Mailing.created_by == current_user.id)
        .options(selectinload(Mailing.messages), selectinload(Mailing.batches))
    )
