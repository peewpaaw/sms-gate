from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.db.session import async_session_factory
from app.domains.auth.enums import UserRole
from app.domains.auth.models import User
from app.domains.auth.services import hash_password
from app.domains.mailing.application.sending_service import MailingSendingService
from app.domains.mailing.enums import (
    MailingStatus,
    MessageStatus,
    MessagesBatchStatus,
)
from app.domains.mailing.models import Mailing, Message, MessagesBatch
from app.domains.providers.base.provider import (
    ProviderOneMessageSendResponse,
    ProviderSendResponse,
)
from app.messaging.outbox.enums import OutboxEventType, OutboxStatus
from app.messaging.outbox.models import Outbox
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.outbox.schemas import OutboxCreate
from app.messaging.schemas import SendBatchTask
from app.workers import publisher as publisher_mod
from app.workers.consumer import send_task


async def _seed_user() -> User:
    async with async_session_factory() as session:
        user = User(
            password_hash=hash_password("test-password"),
            role=UserRole.USER,
            name="worker-test",
            email=f"worker-{uuid4()}@example.com",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.expunge(user)
        return user


async def _seed_outbox(payload: dict, *, event_type=OutboxEventType.SEND_BATCH) -> Outbox:
    async with async_session_factory() as session:
        repo = OutboxRepository(session)
        row = await repo.create(OutboxCreate(event_type=event_type, payload=payload))
        await session.commit()
        outbox_id = row.id
    async with async_session_factory() as session:
        row = await session.get(Outbox, outbox_id)
        assert row is not None
        session.expunge(row)
        return row


async def _get_outbox(outbox_id) -> Outbox:
    async with async_session_factory() as session:
        row = await session.get(Outbox, outbox_id)
        assert row is not None
        session.expunge(row)
        return row


async def _seed_batch(
    *,
    status: MessagesBatchStatus = MessagesBatchStatus.QUEUED,
    message_external_id: str | None = None,
    message_status: MessageStatus = MessageStatus.QUEUED,
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
            status=status,
            messages_count=1,
        )
        session.add(batch)
        await session.flush()
        message = Message(
            mailing_id=mailing.id,
            batch_id=batch.id,
            msisdn="375291234567",
            text="hi",
            status=message_status,
            external_id=message_external_id,
        )
        session.add(message)
        await session.commit()
        mailing_id, batch_id, message_id = mailing.id, batch.id, message.id

    async with async_session_factory() as session:
        mailing = await session.get(Mailing, mailing_id)
        batch = await session.get(MessagesBatch, batch_id)
        message = await session.get(Message, message_id)
        assert mailing and batch and message
        session.expunge_all()
        return mailing, batch, message


@pytest.mark.asyncio
async def test_publish_once_keeps_success_when_later_row_fails(monkeypatch) -> None:
    valid_payload = {
        "mailing_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "provider_code": "fake",
    }
    row1 = await _seed_outbox(valid_payload)
    row2 = await _seed_outbox(valid_payload)

    calls = {"n": 0}

    async def fake_publish(channel, *, routing_key, payload):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("broker down")

    monkeypatch.setattr(publisher_mod, "_publish_payload", fake_publish)

    channel = MagicMock()
    processed = await publisher_mod.publish_once(channel)
    assert processed == 2

    first = await _get_outbox(row1.id)
    second = await _get_outbox(row2.id)
    assert first.status == OutboxStatus.PUBLISHED
    assert second.status == OutboxStatus.FAILED
    assert second.next_retry_at is not None


@pytest.mark.asyncio
async def test_publish_once_invalid_payload_marks_failed_without_publish(
    monkeypatch,
) -> None:
    row = await _seed_outbox({"broken": True})
    published = []

    async def fake_publish(channel, *, routing_key, payload):
        published.append(payload)

    monkeypatch.setattr(publisher_mod, "_publish_payload", fake_publish)

    processed = await publisher_mod.publish_once(MagicMock())
    assert processed == 1
    assert published == []

    updated = await _get_outbox(row.id)
    assert updated.status == OutboxStatus.FAILED


@pytest.mark.asyncio
async def test_apply_send_response_extra_ids_still_full() -> None:
    mailing, batch, message = await _seed_batch(status=MessagesBatchStatus.SENDING)

    async with async_session_factory() as session:
        async with session.begin():
            service = MailingSendingService(session)
            is_full = await service.apply_send_response(
                batch.id,
                ProviderSendResponse(
                    status=True,
                    messages=[
                        ProviderOneMessageSendResponse(
                            message_id=message.id, external_id="ext-1"
                        ),
                        ProviderOneMessageSendResponse(
                            message_id=uuid4(), external_id="extra"
                        ),
                    ],
                ),
            )
            assert is_full is True

    async with async_session_factory() as session:
        refreshed = await session.get(MessagesBatch, batch.id)
        refreshed_mailing = await session.get(Mailing, mailing.id)
        assert refreshed is not None
        assert refreshed_mailing is not None
        assert refreshed.status == MessagesBatchStatus.SUBMITTED
        assert refreshed_mailing.status == MailingStatus.SUBMITTED


@pytest.mark.asyncio
async def test_mailing_stays_queued_until_all_batches_submitted() -> None:
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
        batch_a = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.SENDING,
            messages_count=1,
        )
        batch_b = MessagesBatch(
            mailing_id=mailing.id,
            provider_code="fake",
            status=MessagesBatchStatus.QUEUED,
            messages_count=1,
        )
        session.add_all([batch_a, batch_b])
        await session.flush()
        msg_a = Message(
            mailing_id=mailing.id,
            batch_id=batch_a.id,
            msisdn="375291234567",
            text="a",
            status=MessageStatus.QUEUED,
        )
        session.add(msg_a)
        await session.commit()
        mailing_id, batch_a_id, msg_a_id = mailing.id, batch_a.id, msg_a.id

    async with async_session_factory() as session:
        async with session.begin():
            await MailingSendingService(session).apply_send_response(
                batch_a_id,
                ProviderSendResponse(
                    status=True,
                    messages=[
                        ProviderOneMessageSendResponse(
                            message_id=msg_a_id, external_id="ext-a"
                        ),
                    ],
                ),
            )

    async with async_session_factory() as session:
        refreshed_mailing = await session.get(Mailing, mailing_id)
        refreshed_a = await session.get(MessagesBatch, batch_a_id)
        assert refreshed_mailing is not None
        assert refreshed_a is not None
        assert refreshed_a.status == MessagesBatchStatus.SUBMITTED
        assert refreshed_mailing.status == MailingStatus.QUEUED


@pytest.mark.asyncio
async def test_apply_send_response_terminal_noop() -> None:
    _, batch, message = await _seed_batch(status=MessagesBatchStatus.SUBMITTED)

    async with async_session_factory() as session:
        async with session.begin():
            service = MailingSendingService(session)
            is_full = await service.apply_send_response(
                batch.id,
                ProviderSendResponse(
                    status=True,
                    messages=[
                        ProviderOneMessageSendResponse(
                            message_id=message.id, external_id="should-not-apply"
                        ),
                    ],
                ),
            )
            assert is_full is True

    async with async_session_factory() as session:
        msg = await session.get(Message, message.id)
        assert msg is not None
        assert msg.external_id is None


@pytest.mark.asyncio
async def test_mark_as_queued_preserves_submitted_with_external_id() -> None:
    _, batch, message = await _seed_batch(
        status=MessagesBatchStatus.SENDING,
        message_external_id="keep-me",
        message_status=MessageStatus.SUBMITTED,
    )

    async with async_session_factory() as session:
        async with session.begin():
            await MailingSendingService(session).mark_as_queued(batch.id)

    async with async_session_factory() as session:
        refreshed_batch = await session.get(MessagesBatch, batch.id)
        refreshed_msg = await session.get(Message, message.id)
        assert refreshed_batch is not None
        assert refreshed_msg is not None
        assert refreshed_batch.status == MessagesBatchStatus.QUEUED
        assert refreshed_msg.status == MessageStatus.SUBMITTED
        assert refreshed_msg.external_id == "keep-me"


@pytest.mark.asyncio
async def test_begin_send_recovers_sending(monkeypatch) -> None:
    _, batch, _message = await _seed_batch(status=MessagesBatchStatus.SENDING)

    sent = []

    class FakeProvider:
        code = "fake"
        max_batch_size = 10

        async def send(self, provider_batch):
            sent.append(provider_batch)
            return ProviderSendResponse(
                status=True,
                messages=[
                    ProviderOneMessageSendResponse(
                        message_id=m.message_id, external_id=f"e-{m.message_id}"
                    )
                    for m in provider_batch.messages
                ],
            )

        async def get_status(self, external_id: str):
            raise NotImplementedError

    async def fake_get(code: str):
        return FakeProvider()

    monkeypatch.setattr(
        "app.workers.consumer.provider_registry.get", fake_get
    )

    await send_task(
        SendBatchTask(
            mailing_id=uuid4(),
            batch_id=batch.id,
            provider_code="fake",
        )
    )
    assert len(sent) == 1

    async with async_session_factory() as session:
        refreshed = await session.get(MessagesBatch, batch.id)
        refreshed_mailing = await session.get(Mailing, batch.mailing_id)
        assert refreshed is not None
        assert refreshed_mailing is not None
        assert refreshed.status == MessagesBatchStatus.SUBMITTED
        assert refreshed_mailing.status == MailingStatus.SUBMITTED


@pytest.mark.asyncio
async def test_begin_send_skips_submitted(monkeypatch) -> None:
    _, batch, _message = await _seed_batch(status=MessagesBatchStatus.SUBMITTED)

    called = False

    class FakeProvider:
        code = "fake"
        max_batch_size = 10

        async def send(self, provider_batch):
            nonlocal called
            called = True
            return ProviderSendResponse(status=True, messages=[])

        async def get_status(self, external_id: str):
            raise NotImplementedError

    async def fake_get(code: str):
        return FakeProvider()

    monkeypatch.setattr(
        "app.workers.consumer.provider_registry.get", fake_get
    )

    await send_task(
        SendBatchTask(
            mailing_id=uuid4(),
            batch_id=batch.id,
            provider_code="fake",
        )
    )
    assert called is False
