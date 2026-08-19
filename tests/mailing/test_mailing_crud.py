from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domains.mailing.enums import MailingStatus
from tests.conftest import API_PREFIX, set_mailing_status


def _assert_recent_utc(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    delta = abs(datetime.now(timezone.utc) - parsed.astimezone(timezone.utc))
    assert delta < timedelta(seconds=5)


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


@pytest.mark.asyncio
async def test_create_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    data = await _create_mailing(client, auth_headers, mailing_payload())
    assert data["status"] == MailingStatus.CREATED
    assert data["name"] == "test mailing"
    _assert_recent_utc(data["send_on"])
    assert len(data["messages"]) == 1
    assert data["messages"][0]["msisdn"] == "375291234567"
    assert data["messages"][0]["text"] == "test message"


@pytest.mark.asyncio
async def test_create_mailing_with_send_on(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    send_on = datetime(2026, 7, 8, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    data = await _create_mailing(
        client,
        auth_headers,
        mailing_payload(send_on=send_on.isoformat()),
    )
    stored = datetime.fromisoformat(data["send_on"])
    assert stored.astimezone(timezone.utc) == send_on.astimezone(timezone.utc)


@pytest.mark.asyncio
async def test_update_mailing_without_send_on_sets_now(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    send_on = datetime(2026, 7, 8, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    created = await _create_mailing(
        client,
        auth_headers,
        mailing_payload(send_on=send_on.isoformat()),
    )
    mailing_id = created["id"]

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}",
        json={
            "provider_code": "fake",
            "name": "updated mailing",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    _assert_recent_utc(response.json()["send_on"])


@pytest.mark.asyncio
async def test_get_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]

    response = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mailing_id
    assert data["messages"][0]["text"] == "test message"


@pytest.mark.asyncio
async def test_get_mailing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        f"{API_PREFIX}/mailings/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Mailing not found"


@pytest.mark.asyncio
async def test_list_mailings(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    await _create_mailing(client, auth_headers, mailing_payload())

    response = await client.get(
        f"{API_PREFIX}/mailings/",
        params={"status": MailingStatus.CREATED, "limit": 10, "offset": 0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] >= 1
    assert any(item["status"] == MailingStatus.CREATED for item in page["items"])


@pytest.mark.asyncio
async def test_update_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]
    old_message_id = created["messages"][0]["id"]

    updated_payload = mailing_payload(
        name="updated mailing",
        messages=[
            {"msisdn": "+375 29 1112233", "text": "updated text"},
            {"msisdn": "375441112233", "text": "second"},
        ],
    )
    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}",
        json=updated_payload,
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "updated mailing"
    assert len(data["messages"]) == 2
    msisdns = {m["msisdn"] for m in data["messages"]}
    assert msisdns == {"375291112233", "375441112233"}
    texts = {m["text"] for m in data["messages"]}
    assert texts == {"updated text", "second"}
    new_ids = {m["id"] for m in data["messages"]}
    assert old_message_id not in new_ids


@pytest.mark.asyncio
async def test_update_mailing_without_messages_keeps_messages(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]
    message_id = created["messages"][0]["id"]

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}",
        json={"provider_code": "fake", "name": "test mailing"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["id"] == message_id
    assert data["messages"][0]["text"] == "test message"


@pytest.mark.asyncio
async def test_update_mailing_empty_messages_clears(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}",
        json={"provider_code": "fake", "name": "test mailing", "messages": []},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["messages"] == []


@pytest.mark.asyncio
async def test_update_mailing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    response = await client.put(
        f"{API_PREFIX}/mailings/{uuid4()}",
        json=mailing_payload(),
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Mailing not found"


@pytest.mark.asyncio
async def test_update_mailing_forbidden_when_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]
    await set_mailing_status(mailing_id, MailingStatus.QUEUED)

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}",
        json=mailing_payload(),
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Mailing can be updated only in created status"


@pytest.mark.asyncio
async def test_delete_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]

    delete_response = await client.delete(
        f"{API_PREFIX}/mailings/{mailing_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    get_response = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_mailing_forbidden_when_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    created = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = created["id"]
    await set_mailing_status(mailing_id, MailingStatus.QUEUED)

    response = await client.delete(
        f"{API_PREFIX}/mailings/{mailing_id}",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Mailing can be deleted only in created status"


@pytest.mark.asyncio
async def test_delete_mailing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.delete(
        f"{API_PREFIX}/mailings/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Mailing not found"
