import hashlib
import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.messaging.publisher import publish_send_batch
from app.messaging.schemas import SendBatchTask
from app.models.idempotency_key import IdempotencyKey
from app.models.sms_batch import SmsBatch
from app.models.user import User
from app.schemas.mailing import MailingCreate, MailingCreateResponse
from app.services.mailing import create_mailing


def request_hash(payload: MailingCreate) -> str:
    body = payload.model_dump(mode="json")
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def create_mailing_idempotently(
    session: AsyncSession,
    current_user: User,
    payload: MailingCreate,
    key: str,
    correlation_id: str | None,
) -> MailingCreateResponse:
    digest = request_hash(payload)
    existing = await session.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.key == key,
        )
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used with a different request body",
            )
        if existing.response_payload is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotent request is still being processed",
            )
        return MailingCreateResponse.model_validate(existing.response_payload)

    idempotency_key = IdempotencyKey(
        user_id=current_user.id,
        key=key,
        request_hash=digest,
        status_code=status.HTTP_201_CREATED,
    )
    session.add(idempotency_key)

    response = await create_mailing(
        session,
        current_user,
        payload,
        correlation_id=correlation_id,
        publish=False,
        commit=False,
    )
    idempotency_key.response_payload = response.model_dump(mode="json")
    await session.commit()

    batches = (
        await session.scalars(select(SmsBatch).where(SmsBatch.mailing_id == response.mailing_id))
    ).all()
    for batch in batches:
        await publish_send_batch(
            SendBatchTask(
                batch_id=batch.id,
                mailing_id=response.mailing_id,
                provider_code=batch.provider_code,
                correlation_id=correlation_id,
            )
        )

    return response
