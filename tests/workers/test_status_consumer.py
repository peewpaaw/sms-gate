from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.session import async_session_factory
from app.domains.auth.enums import UserRole
from app.domains.auth.models import User
from app.domains.auth.services import hash_password
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
            password_hash=hash_password("test-password"),
            role=UserRole.USER,
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
    mailing_status: MailingStatus = MailingStatus.SUBMITTED,
) -> tuple[Mailing, MessagesBatch, Message]:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=mailing_status,
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
    mailing, batch, message = await _seed_submitted_message()

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
        refreshed_mailing = await session.get(Mailing, mailing.id)
        assert refreshed is not None
        assert refreshed_batch is not None
        assert refreshed_mailing is not None
        assert refreshed.status == MessageStatus.DELIVERED
        assert refreshed_batch.status == MessagesBatchStatus.COMPLETED
        assert refreshed_mailing.status == MailingStatus.DELIVERED


@pytest.mark.asyncio
async def test_apply_status_no_regress_from_delivered() -> None:
    _, _batch, message = await _seed_submitted_message(status=MessageStatus.DELIVERED)

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
async def test_mailing_delivered_when_all_messages_delivered() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=2,
        )
        session.add(batch)
        await session.flush()
        msg_a = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291111111",
            text="a",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_b = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375292222222",
            text="b",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        session.add_all([msg_a, msg_b])
        await session.commit()
        mailing_id, msg_a_id, msg_b_id = mailing.id, msg_a.id, msg_b.id
        msisdn_a, msisdn_b = msg_a.msisdn, msg_b.msisdn

    for message_id, msisdn in ((msg_a_id, msisdn_a), (msg_b_id, msisdn_b)):
        async with async_session_factory() as session:
            async with session.begin():
                await MessageStatusService(session).apply_status_response(
                    message_id,
                    ProviderStatusResponse(
                        status="ok",
                        messages_status=[
                            ProviderOneMessageStatusResponse(
                                message_id=None,
                                msisdn=msisdn,
                                status=MessageStatus.DELIVERED,
                            )
                        ],
                    ),
                )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        assert refreshed is not None
        assert refreshed.status == MailingStatus.DELIVERED


@pytest.mark.asyncio
async def test_mailing_delivered_when_one_delivered_one_failed() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=2,
        )
        session.add(batch)
        await session.flush()
        msg_ok = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291111111",
            text="ok",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_fail = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375292222222",
            text="fail",
            status=MessageStatus.FAILED,
            external_id=None,
        )
        session.add_all([msg_ok, msg_fail])
        await session.commit()
        mailing_id, msg_ok_id, msisdn = mailing.id, msg_ok.id, msg_ok.msisdn

    async with async_session_factory() as session:
        async with session.begin():
            await MessageStatusService(session).apply_status_response(
                msg_ok_id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=msisdn,
                            status=MessageStatus.DELIVERED,
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        assert refreshed is not None
        assert refreshed.status == MailingStatus.DELIVERED


@pytest.mark.asyncio
async def test_mailing_undelivered_when_mix_undelivered_and_failed() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=2,
        )
        session.add(batch)
        await session.flush()
        msg_undel = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291111111",
            text="undel",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_fail = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375292222222",
            text="fail",
            status=MessageStatus.FAILED,
            external_id=None,
        )
        session.add_all([msg_undel, msg_fail])
        await session.commit()
        mailing_id, msg_id, msisdn = mailing.id, msg_undel.id, msg_undel.msisdn

    async with async_session_factory() as session:
        async with session.begin():
            await MessageStatusService(session).apply_status_response(
                msg_id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=msisdn,
                            status=MessageStatus.UNDELIVERED,
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        assert refreshed is not None
        assert refreshed.status == MailingStatus.UNDELIVERED


@pytest.mark.asyncio
async def test_mailing_failed_when_all_messages_failed() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=2,
        )
        session.add(batch)
        await session.flush()
        msg_a = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291111111",
            text="a",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_b = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375292222222",
            text="b",
            status=MessageStatus.FAILED,
            external_id=None,
        )
        session.add_all([msg_a, msg_b])
        await session.commit()
        mailing_id, msg_a_id, msisdn = mailing.id, msg_a.id, msg_a.msisdn

    async with async_session_factory() as session:
        async with session.begin():
            await MessageStatusService(session).apply_status_response(
                msg_a_id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=msisdn,
                            status=MessageStatus.FAILED,
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        assert refreshed is not None
        assert refreshed.status == MailingStatus.FAILED


@pytest.mark.asyncio
async def test_mailing_stays_submitted_while_message_pending() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=2,
        )
        session.add(batch)
        await session.flush()
        msg_done = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291111111",
            text="done",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_pending = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375292222222",
            text="pending",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        session.add_all([msg_done, msg_pending])
        await session.commit()
        mailing_id, msg_done_id, msisdn = mailing.id, msg_done.id, msg_done.msisdn

    async with async_session_factory() as session:
        async with session.begin():
            await MessageStatusService(session).apply_status_response(
                msg_done_id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=msisdn,
                            status=MessageStatus.DELIVERED,
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        assert refreshed is not None
        assert refreshed.status == MailingStatus.SUBMITTED


@pytest.mark.asyncio
async def test_mailing_stays_submitted_until_all_batches_terminal() -> None:
    user = await _seed_user()
    async with async_session_factory() as session:
        mailing = Mailing(
            provider_code="fake",
            name="test mailing",
            status=MailingStatus.SUBMITTED,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        session.add(mailing)
        await session.flush()
        batch_a = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=1,
        )
        batch_b = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SUBMITTED,
            messages_count=1,
        )
        session.add_all([batch_a, batch_b])
        await session.flush()
        msg_a = Message(
            mailing_id=mailing.id,
            batch_id=batch_a.id,
            msisdn="375291111111",
            text="a",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        msg_b = Message(
            mailing_id=mailing.id,
            batch_id=batch_b.id,
            msisdn="375292222222",
            text="b",
            status=MessageStatus.SUBMITTED,
            external_id=str(uuid4()),
        )
        session.add_all([msg_a, msg_b])
        await session.commit()
        mailing_id = mailing.id
        batch_a_id = batch_a.id
        msg_a_id = msg_a.id
        msisdn = msg_a.msisdn

    async with async_session_factory() as session:
        async with session.begin():
            await MessageStatusService(session).apply_status_response(
                msg_a_id,
                ProviderStatusResponse(
                    status="ok",
                    messages_status=[
                        ProviderOneMessageStatusResponse(
                            message_id=None,
                            msisdn=msisdn,
                            status=MessageStatus.DELIVERED,
                        )
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed = await session.get(Mailing, mailing_id)
        batch_a_ref = await session.get(MessagesBatch, batch_a_id)
        assert refreshed is not None
        assert batch_a_ref is not None
        assert batch_a_ref.status == MessagesBatchStatus.COMPLETED
        assert refreshed.status == MailingStatus.SUBMITTED


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

    monkeypatch.setattr("app.workers.status_consumer.provider_registry.get", fake_get)

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

    monkeypatch.setattr("app.workers.status_consumer.provider_registry.get", fake_get)

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
