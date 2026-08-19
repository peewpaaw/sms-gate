from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import API_PREFIX, basic_auth_header


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/users/me/")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").lower().startswith("basic")


@pytest.mark.asyncio
async def test_me_wrong_password(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get(
        f"{API_PREFIX}/users/me/",
        headers=basic_auth_header(f"missing-{uuid4()}@example.com", "wrong-password"),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_ok(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get(f"{API_PREFIX}/users/me/", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_user_forbidden_on_users_create(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        f"{API_PREFIX}/users/",
        headers=auth_headers,
        json={
            "email": f"new-{uuid4()}@example.com",
            "password": "password123",
            "name": "x",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_forbidden_on_provider_patch(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.patch(
        f"{API_PREFIX}/providers/fake",
        headers=auth_headers,
        json={"is_enabled": True},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_creates_user(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    email = f"created-{uuid4()}@example.com"
    response = await client.post(
        f"{API_PREFIX}/users/",
        headers=admin_headers,
        json={
            "email": email,
            "password": "password123",
            "name": "Created",
            "role": "user",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "user"

    login = await client.get(
        f"{API_PREFIX}/users/me/",
        headers=basic_auth_header(email, "password123"),
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_cannot_demote_last_admin(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """A is fixture admin; create B; demote A (ok); demote B when sole -> 409."""
    me_a = await client.get(f"{API_PREFIX}/users/me/", headers=admin_headers)
    assert me_a.status_code == 200
    admin_a_id = me_a.json()["id"]

    email_b = f"last-admin-{uuid4()}@example.com"
    create_b = await client.post(
        f"{API_PREFIX}/users/",
        headers=admin_headers,
        json={
            "email": email_b,
            "password": "password123",
            "name": "Admin B",
            "role": "admin",
        },
    )
    assert create_b.status_code == 201
    admin_b_id = create_b.json()["id"]
    headers_b = basic_auth_header(email_b, "password123")

    # Demote A while B exists — allowed regardless of other leftover admins
    demote_a = await client.patch(
        f"{API_PREFIX}/users/{admin_a_id}/",
        headers=headers_b,
        json={"role": "user"},
    )
    assert demote_a.status_code == 200

    # Deactivate every other active admin except B, then demote B
    listed = await client.get(f"{API_PREFIX}/users/?limit=500", headers=headers_b)
    assert listed.status_code == 200
    for item in listed.json()["items"]:
        if item["id"] == admin_b_id:
            continue
        if item["role"] == "admin" and item["is_active"]:
            resp = await client.patch(
                f"{API_PREFIX}/users/{item['id']}/",
                headers=headers_b,
                json={"is_active": False},
            )
            assert resp.status_code == 200

    blocked = await client.patch(
        f"{API_PREFIX}/users/{admin_b_id}/",
        headers=headers_b,
        json={"role": "user"},
    )
    assert blocked.status_code == 409
    assert "last active admin" in blocked.json()["detail"].lower()

    blocked_deactivate = await client.patch(
        f"{API_PREFIX}/users/{admin_b_id}/",
        headers=headers_b,
        json={"is_active": False},
    )
    assert blocked_deactivate.status_code == 409
