import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domains.auth.enums import UserRole
from tests.conftest import API_PREFIX, _insert_user


async def _create_mailing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    messages: list[dict],
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/mailings/",
        json={
            "provider_code": "fake",
            "name": "stats mailing",
            "messages": messages,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _other_user_headers() -> dict[str, str]:
    return _insert_user(
        email=f"other-{uuid4()}@example.com",
        password=secrets.token_urlsafe(16),
        role=UserRole.USER,
        name="other",
    )


def _period_params() -> dict[str, str]:
    today = datetime.now(timezone.utc).date()
    return {
        "date_from": (today - timedelta(days=1)).isoformat(),
        "date_to": today.isoformat(),
        "timezone": "UTC",
    }


@pytest.mark.asyncio
async def test_message_stats_user_sees_only_own(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    await _create_mailing(
        client,
        auth_headers,
        messages=[
            {"msisdn": "375291111111", "text": "a1"},
            {"msisdn": "375291111112", "text": "a2"},
        ],
    )
    other_headers = _other_user_headers()
    await _create_mailing(
        client,
        other_headers,
        messages=[
            {"msisdn": "375292222221", "text": "b1"},
            {"msisdn": "375292222222", "text": "b2"},
            {"msisdn": "375292222223", "text": "b3"},
        ],
    )

    response = await client.get(
        f"{API_PREFIX}/stats/messages-by-provider",
        params=_period_params(),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    total = sum(item["count"] for item in response.json()["items"])
    assert total == 2


@pytest.mark.asyncio
async def test_message_stats_admin_sees_all(
    client: AsyncClient,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    await _create_mailing(
        client,
        auth_headers,
        messages=[
            {"msisdn": "375291111111", "text": "a1"},
            {"msisdn": "375291111112", "text": "a2"},
        ],
    )
    other_headers = _other_user_headers()
    await _create_mailing(
        client,
        other_headers,
        messages=[
            {"msisdn": "375292222221", "text": "b1"},
            {"msisdn": "375292222222", "text": "b2"},
            {"msisdn": "375292222223", "text": "b3"},
        ],
    )

    response = await client.get(
        f"{API_PREFIX}/stats/messages-by-provider",
        params=_period_params(),
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    total = sum(item["count"] for item in response.json()["items"])
    assert total == 5
