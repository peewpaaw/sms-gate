from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.session import async_session_factory
from app.domains.auth.models import User
from app.domains.auth.services import hash_api_key
from app.domains.mailing.application.sending_service import MailingSendingService
from app.domains.mailing.application.status_service import (
    MessageStatusService,
    StatusNotReady,
)
from app.domains.mailing.enums import (
    MailingStatus,
    MessageStatus,
    MessagesBatchStatus,
)
from app.domains.mailing.models import Mailing, Message, MessagesBatch
from app.domains.providers.base.provider import (
    ProviderOneMessageSendResponse,
    ProviderOneMessageStatusResponse,
    ProviderSendResponse,
    ProviderStatusResponse,
)
from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.models import Outbox
from app.messaging.schemas import GetMessageStatusTask
from app.workers.status_consumer import check_status
from sqlalchemy import select


async def _seed_user() -> User:
    async with async_session_factory() as session:
        user = User(
            api_key_hash=hash_api_key(f"status-{uuid4()}"),
            name="status-test",
            email=f"status-{uuid4()}@example.com",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.expunge(user)
        return user


async def _seed_submitted_message(
    *,
    msisdn: str = "375291234567",
    status: MessageStatus = MessageStatus.SUBMITTED,
) -> tuple[Mailing, MessagesBatch, Message]:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.QUEUED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=1,
        )
        session.add(batch)
        await session.flush()
        message = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn=msisdn,
            text="hi",
            status=status,
            external_id=str(uuid4()),
        )
        session.add(message)
        await session.commit()
        ids = (mailing.id, batch.id, message.id)

    async with async_session_factory() as session:
        mailing = await session.get(Mailing, ids[0])
        batch = await session.get(MessagesBatch, ids[1])
        message = await session.get(Message, ids[2])
        assert mailing and batch and message
        session.expunge_all()
        return mailing, batch, message


@pytest.mark.asyncio
async def test_apply_status_submitted_to_delivered() -> None:
    _, batch, message = await _seed_submitted_message()

    async with async_session_factory() as session:
        async with session.begin():
            status = await MessageStatusService(session).apply_status_response(
                message.id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=message.msisdn,
                            status=MessageStatus.DELIVERED,
                        )
                    ],
                ),
            )
            assert status == MessageStatus.DELIVERED

    async with async_session_factory() as session:
        refreshed = await session.get(Message, message.id)
        refreshed_batch = await session.get(MessagesBatch, batch.id)
        assert refreshed is not None
        assert refreshed_batch is not None
        assert refreshed.status == MessageStatus.DELIVERED
        assert refreshed_batch.status == MessagesBatchStatus.COMPLETED


@pytest.mark.asyncio
async def test_apply_status_no_regress_from_delivered() -> None:
    _, _batch, message = await _seed_submitted_message(
        status=MessageStatus.DELIVERED
    )

    async with async_session_factory() as session:
        async with session.begin():
            status = await MessageStatusService(session).apply_status_response(
                message.id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=message.id,
                            msisdn=None,
                            status=MessageStatus.SUBMITTED,
                        )
                    ],
                ),
            )
            assert status == MessageStatus.DELIVERED

    async with async_session_factory() as session:
        refreshed = await session.get(Message, message.id)
        assert refreshed is not None
        assert refreshed.status == MessageStatus.DELIVERED


@pytest.mark.asyncio
async def test_apply_status_anonymous_single_item() -> None:
    _, _batch, message = await _seed_submitted_message()

    async with async_session_factory() as session:
        async with session.begin():
            status = await MessageStatusService(session).apply_status_response(
                message.id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=None,
                            status=MessageStatus.DELIVERED,
                        )
                    ],
                ),
            )
            assert status == MessageStatus.DELIVERED


@pytest.mark.asyncio
async def test_apply_send_response_enqueues_check_status() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.QUEUED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SENDING,
            messages_count=1,
        )
        session.add(batch)
        await session.flush()
        message = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291234567",
            text="hi",
            status=MessageStatus.QUEUED,
        )
        session.add(message)
        await session.commit()
        batch_id, message_id = batch.id, message.id

    async with async_session_factory() as session:
        async with session.begin():
            await MailingSendingService(session).apply_send_response(
                batch_id,
                ProviderSendResponse(
                    status=True,
                    messages=[
                        ProviderOneMessageSendResponse(
                            message_id=message_id, external_id="sid-1"
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        rows = list(await session.scalars(select(Outbox)))
        status_rows = [
            row for row in rows if row.event_type == OutboxEventType.CHECK_STATUS
        ]
        assert len(status_rows) == 1
        assert status_rows[0].payload["message_id"] == str(message_id)
        assert status_rows[0].payload["external_id"] == "sid-1"
        assert status_rows[0].payload["provider_code"] == "fake"


@pytest.mark.asyncio
async def test_check_status_raises_not_ready_when_still_submitted(monkeypatch) -> None:
    _, _batch, message = await _seed_submitted_message()

    class StickyProvider:
        code = "fake"
        max_batch_size = 1

        async def send(self, batch):
            raise NotImplementedError

        async def get_status(self, external_id: str):
            return ProviderStatusResponse(
                status="pending",
                messages_status=[
                    ProviderOneMessageStatusResponse(
                        message_id=None,
                        msisdn=None,
                        status=MessageStatus.SUBMITTED,
                    )
                ],
            )

    async def fake_get(code: str):
        return StickyProvider()

    monkeypatch.setattr(
        "app.workers.status_consumer.provider_registry.get", fake_get
    )

    with pytest.raises(StatusNotReady):
        await check_status(
            GetMessageStatusTask(
                message_id=message.id,
                external_id=message.external_id or "x",
                provider_code="fake",
            )
        )


@pytest.mark.asyncio
async def test_check_status_completes_when_delivered(monkeypatch) -> None:
    _, batch, message = await _seed_submitted_message()

    class DoneProvider:
        code = "fake"
        max_batch_size = 1

        async def send(self, batch):
            raise NotImplementedError

        async def get_status(self, external_id: str):
            return ProviderStatusResponse(
                status="ok",
                messages_status=[
                    ProviderOneMessageStatusResponse(
                        message_id=None,
                        msisdn=None,
                        status=MessageStatus.DELIVERED,
                    )
                ],
            )

    async def fake_get(code: str):
        return DoneProvider()

    monkeypatch.setattr(
        "app.workers.status_consumer.provider_registry.get", fake_get
    )

    await check_status(
        GetMessageStatusTask(
            message_id=message.id,
            external_id=message.external_id or "x",
            provider_code="fake",
        )
    )

    async with async_session_factory() as session:
        refreshed = await session.get(Message, message.id)
        refreshed_batch = await session.get(MessagesBatch, batch.id)
        assert refreshed is not None
        assert refreshed_batch is not None
        assert refreshed.status == MessageStatus.DELIVERED
        assert refreshed_batch.status == MessagesBatchStatus.COMPLETED
