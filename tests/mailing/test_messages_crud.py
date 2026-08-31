from uuid import uuid4
import secrets

import pytest
from httpx import AsyncClient

from app.domains.auth.enums import UserRole
from app.domains.mailing.enums import MailingStatus, MessageStatus
from tests.conftest import API_PREFIX, _insert_user, set_mailing_status, set_message_status


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
async def test_create_mailing_with_empty_messages(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    data = await _create_mailing(
        client,
        auth_headers,
        {"provider_code": "fake", "name": "test mailing", "messages": []},
    )
    assert data["status"] == MailingStatus.CREATED
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_create_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    mailing = await _create_mailing(
        client, auth_headers, {"provider_code": "fake", "name": "test mailing", "messages": []}
    )
    mailing_id = mailing["id"]

    response = await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/",
        json={"msisdn": "375291234567", "text": "nested create"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    message = response.json()
    assert message["msisdn"] == "375291234567"
    assert message["text"] == "nested create"
    assert message["status"] == MessageStatus.CREATED
    assert "send_on" not in message

    get_mailing = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}",
        headers=auth_headers,
    )
    assert len(get_mailing.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_get_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    mailing = await _create_mailing(
        client, auth_headers, {"provider_code": "fake", "name": "test mailing", "messages": []}
    )
    mailing_id = mailing["id"]
    created = await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/",
        json={"msisdn": "375291234567", "text": "hello"},
        headers=auth_headers,
    )
    message_id = created.json()["id"]

    response = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["text"] == "hello"


@pytest.mark.asyncio
async def test_update_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    mailing = await _create_mailing(
        client, auth_headers, {"provider_code": "fake", "name": "test mailing", "messages": []}
    )
    mailing_id = mailing["id"]
    created = await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/",
        json={"msisdn": "375291234567", "text": "before"},
        headers=auth_headers,
    )
    message_id = created.json()["id"]

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        json={"msisdn": "+375 29 9998877", "text": "after"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["msisdn"] == "375299998877"
    assert data["text"] == "after"


@pytest.mark.asyncio
async def test_delete_message(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    mailing = await _create_mailing(
        client, auth_headers, {"provider_code": "fake", "name": "test mailing", "messages": []}
    )
    mailing_id = mailing["id"]
    created = await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/",
        json={"msisdn": "375291234567", "text": "to delete"},
        headers=auth_headers,
    )
    message_id = created.json()["id"]

    delete_response = await client.delete(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    get_response = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_get_message_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    mailing = await _create_mailing(
        client, auth_headers, {"provider_code": "fake", "name": "test mailing", "messages": []}
    )
    response = await client.get(
        f"{API_PREFIX}/mailings/{mailing['id']}/messages/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Message not found"


@pytest.mark.asyncio
async def test_create_message_mailing_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        f"{API_PREFIX}/mailings/{uuid4()}/messages/",
        json={"msisdn": "375291234567", "text": "x"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Mailing not found"


@pytest.mark.asyncio
async def test_create_message_forbidden_when_mailing_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    mailing = await _create_mailing(client, auth_headers, mailing_payload())
    await set_mailing_status(mailing["id"], MailingStatus.QUEUED)

    response = await client.post(
        f"{API_PREFIX}/mailings/{mailing['id']}/messages/",
        json={"msisdn": "375441112233", "text": "late"},
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_message_forbidden_when_message_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    mailing = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = mailing["id"]
    message_id = mailing["messages"][0]["id"]
    await set_message_status(message_id, MessageStatus.QUEUED)

    response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        json={"msisdn": "375291234567", "text": "nope"},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Message can be modified only in created status"


@pytest.mark.asyncio
async def test_delete_message_forbidden_when_message_not_created(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    mailing = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = mailing["id"]
    message_id = mailing["messages"][0]["id"]
    await set_message_status(message_id, MessageStatus.QUEUED)

    response = await client.delete(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=auth_headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_messages_foreign_mailing_returns_404(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mailing_payload,
) -> None:
    mailing = await _create_mailing(client, auth_headers, mailing_payload())
    mailing_id = mailing["id"]
    message_id = mailing["messages"][0]["id"]
    other_headers = _insert_user(
        email=f"other-{uuid4()}@example.com",
        password=secrets.token_urlsafe(16),
        role=UserRole.USER,
        name="other",
    )

    get_response = await client.get(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=other_headers,
    )
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Mailing not found"

    create_response = await client.post(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/",
        json={"msisdn": "375291234567", "text": "x"},
        headers=other_headers,
    )
    assert create_response.status_code == 404
    assert create_response.json()["detail"] == "Mailing not found"

    update_response = await client.put(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        json={"msisdn": "375291234567", "text": "hijack"},
        headers=other_headers,
    )
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "Mailing not found"

    delete_response = await client.delete(
        f"{API_PREFIX}/mailings/{mailing_id}/messages/{message_id}",
        headers=other_headers,
    )
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Mailing not found"