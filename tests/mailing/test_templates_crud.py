import pytest
from httpx import AsyncClient

from tests.conftest import API_PREFIX


async def _create_template(
    client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    text: str,
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/templates/",
        json={"name": name, "text": text},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_list_templates_search_by_name_or_text(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    by_name = await _create_template(
        client,
        auth_headers,
        name="Promo Alpha Wave",
        text="plain greeting",
    )
    by_text = await _create_template(
        client,
        auth_headers,
        name="Other Campaign",
        text="Contains ALPHA code inside",
    )
    await _create_template(
        client,
        auth_headers,
        name="Unrelated",
        text="no match here",
    )

    response = await client.get(
        f"{API_PREFIX}/templates/",
        params={"search": "alpha", "limit": 10, "offset": 0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert len(page["items"]) == 2
    ids = {item["id"] for item in page["items"]}
    assert ids == {by_name["id"], by_text["id"]}
