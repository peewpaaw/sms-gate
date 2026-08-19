from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing
from app.messaging.outbox.enums import OutboxStatus
from app.messaging.outbox.models import Outbox
from tests.conftest import API_PREFIX, set_mailing_status


async def _create_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    payload: dict,
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/mailings/",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _send_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_id: str,
) -> object:
    return await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/send",
        headers=auth_headers,
    )


async def _load_mailing(mailing_id: UUID) -> Mailing:
    async with async_session_factory() as session:
        mailing = await session.scalar(
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
            )
            .where(Mailing.id == mailing_id)
        )
        assert mailing is not None
        # Detach graph for assertions outside the session.
        _ = list(mailing.messages)
        _ = list(mailing.batches)
        session.expunge(mailing)
        return mailing


async def _count_outbox_for_batches(batch_ids: list[UUID]) -> list[Outbox]:
    async with async_session_factory() as session:
        rows = (
            await session.scalars(select(Outbox).order_by(Outbox.created_at.asc()))
        ).all()
        matched = []
        for row in rows:
            raw_batch_id = row.payload.get("batch_id")
            if raw_batch_id is None:
                continue
            if UUID(str(raw_batch_id)) in set(batch_ids):
                matched.append(row)
        for row in matched:
            session.expunge(row)
        return matched


@pytest.mark.asyncio
async def test_send_mailing_happy_path(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = UUID(created["id"])

    response = await _send_mailing(client, auth_headers, created["id"])
    assert response.status_code == 200, response.text
    assert response.json() == {"message": "Mailing batched"}

    mailing = await _load_mailing(mailing_id)
    assert mailing.status == MailingStatus.QUEUED
    assert len(mailing.messages) == 1
    assert mailing.messages[0].status == MessageStatus.QUEUED
    assert mailing.messages[0].batch_id is not None
    assert len(mailing.batches) == 1
    assert mailing.batches[0].status == MessagesBatchStatus.QUEUED
    assert mailing.batches[0].messages_count == 1

    outbox_rows = await _count_outbox_for_batches([mailing.batches[0].id])
    assert len(outbox_rows) == 1
    assert outbox_rows[0].status == OutboxStatus.PENDING
    assert outbox_rows[0].payload["batch_id"] == str(mailing.batches[0].id)
    assert outbox_rows[0].payload["mailing_id"] == str(mailing_id)
    assert outbox_rows[0].payload["provider_code"] == "fake"


@pytest.mark.asyncio
async def test_send_mailing_chunks_by_max_batch_size(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await _create_mailing(
        client,
        auth_headers,
        {
            "provider_code": "fake",
            "messages": [
                {"msisdn": "375291111111", "text": "one"},
                {"msisdn": "375292222222", "text": "two"},
                {"msisdn": "375293333333", "text": "three"},
            ],
        },
    )
    mailing_id = UUID(created["id"])

    response = await _send_mailing(client, auth_headers, created["id"])
    assert response.status_code == 200, response.text

    mailing = await _load_mailing(mailing_id)
    assert len(mailing.batches) == 3
    assert all(batch.status == MessagesBatchStatus.QUEUED for batch in mailing.batches)
    assert all(message.status == MessageStatus.QUEUED for message in mailing.messages)
    assert {message.batch_id for message in mailing.messages} == {
        batch.id for batch in mailing.batches
    }

    outbox_rows = await _count_outbox_for_batches([batch.id for batch in mailing.batches])
    assert len(outbox_rows) == 3


@pytest.mark.asyncio
async def test_send_mailing_second_call_conflict(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = UUID(created["id"])

    first = await _send_mailing(client, auth_headers, created["id"])
    assert first.status_code == 200, first.text

    second = await _send_mailing(client, auth_headers, created["id"])
    assert second.status_code == 409
    assert second.json()["detail"] == "Mailing can be sent only in created status"

    mailing = await _load_mailing(mailing_id)
    assert len(mailing.batches) == 1
    outbox_rows = await _count_outbox_for_batches([mailing.batches[0].id])
    assert len(outbox_rows) == 1


@pytest.mark.asyncio
async def test_send_mailing_empty_messages(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    created = await _create_mailing(
        client,
        auth_headers,
        {"provider_code": "fake", "messages": []},
    )

    response = await _send_mailing(client, auth_headers, created["id"])
    assert response.status_code == 422
    assert response.json()["detail"] == "Mailing has no messages"


@pytest.mark.asyncio
async def test_send_mailing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await _send_mailing(client, auth_headers, str(uuid4()))
    assert response.status_code == 404
    assert response.json()["detail"] == "Mailing not found"


@pytest.mark.asyncio
async def test_send_mailing_forbidden_when_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    await set_mailing_status(UUID(created["id"]), MailingStatus.QUEUED)

    response = await _send_mailing(client, auth_headers, created["id"])
    assert response.status_code == 409
    assert response.json()["detail"] == "Mailing can be sent only in created status"

    mailing = await _load_mailing(UUID(created["id"]))
    assert mailing.batches == []
