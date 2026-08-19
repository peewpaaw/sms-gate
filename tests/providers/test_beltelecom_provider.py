from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domains.providers.base.provider import ProviderBatch, ProviderMessage
from app.domains.providers.beltelecom.provider import BeltelecomProvider


def _provider() -> BeltelecomProvider:
    provider = BeltelecomProvider(
        base_url="https://example.test",
        username="user",
        password="pass",
    )
    provider._client.get_csrf_token = AsyncMock(return_value="csrf-token")
    return provider


@pytest.mark.asyncio
async def test_beltelecom_send_passes_batch_name_and_send_on_in_payload() -> None:
    provider = _provider()
    provider._client.submit_sms = AsyncMock(return_value={"sid": "sid-1"})

    send_on = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    batch = ProviderBatch(
        name="campaign title",
        send_on=send_on,
        messages=[
            ProviderMessage(
                message_id=uuid4(),
                msisdn="375291234567",
                text="hello",
            )
        ],
    )

    response = await provider.send(batch)

    assert response.status is True
    assert len(response.messages) == 1
    assert response.messages[0].external_id == "sid-1"

    provider._client.submit_sms.assert_awaited_once()
    payload, csrf_token = provider._client.submit_sms.await_args.args
    assert csrf_token == "csrf-token"
    assert payload["name"] == "campaign title"
    assert payload["text"] == "hello"
    assert payload["date_time"] == send_on.isoformat()
    assert payload["ukazhite_nomera_telefonov_do_10_nomerov"] == ["375291234567"]


@pytest.mark.asyncio
async def test_beltelecom_send_groups_same_text() -> None:
    provider = _provider()
    provider._client.submit_sms = AsyncMock(return_value={"sid": "sid-shared"})

    send_on = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    id1, id2 = uuid4(), uuid4()
    batch = ProviderBatch(
        name="campaign",
        send_on=send_on,
        messages=[
            ProviderMessage(message_id=id1, msisdn="375291111111", text="same"),
            ProviderMessage(message_id=id2, msisdn="375292222222", text="same"),
        ],
    )

    response = await provider.send(batch)

    provider._client.submit_sms.assert_awaited_once()
    payload, _ = provider._client.submit_sms.await_args.args
    assert payload["ukazhite_nomera_telefonov_do_10_nomerov"] == [
        "375291111111",
        "375292222222",
    ]
    assert payload["date_time"] == send_on.isoformat()
    assert {item.external_id for item in response.messages} == {"sid-shared"}
    assert {item.message_id for item in response.messages} == {id1, id2}


@pytest.mark.asyncio
async def test_beltelecom_send_splits_different_text() -> None:
    provider = _provider()
    provider._client.submit_sms = AsyncMock(
        side_effect=[{"sid": "sid-a"}, {"sid": "sid-b"}]
    )

    send_on = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    id1, id2 = uuid4(), uuid4()
    batch = ProviderBatch(
        name="campaign",
        send_on=send_on,
        messages=[
            ProviderMessage(message_id=id1, msisdn="375291111111", text="a"),
            ProviderMessage(message_id=id2, msisdn="375292222222", text="b"),
        ],
    )

    response = await provider.send(batch)

    assert provider._client.submit_sms.await_count == 2
    payloads = [call.args[0] for call in provider._client.submit_sms.await_args_list]
    groups = {
        (p["text"], p["date_time"], tuple(p["ukazhite_nomera_telefonov_do_10_nomerov"]))
        for p in payloads
    }
    assert groups == {
        ("a", send_on.isoformat(), ("375291111111",)),
        ("b", send_on.isoformat(), ("375292222222",)),
    }

    by_id = {item.message_id: item.external_id for item in response.messages}
    assert by_id[id1] != by_id[id2]


@pytest.mark.asyncio
async def test_beltelecom_send_skips_messages_with_external_id() -> None:
    provider = _provider()
    provider._client.submit_sms = AsyncMock(return_value={"sid": "sid-new"})

    send_on = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    existing_id, new_id = uuid4(), uuid4()
    batch = ProviderBatch(
        name="campaign",
        send_on=send_on,
        messages=[
            ProviderMessage(
                message_id=existing_id,
                msisdn="375291111111",
                text="same",
                external_id="sid-old",
            ),
            ProviderMessage(
                message_id=new_id,
                msisdn="375292222222",
                text="same",
            ),
        ],
    )

    response = await provider.send(batch)

    provider._client.submit_sms.assert_awaited_once()
    payload, _ = provider._client.submit_sms.await_args.args
    assert payload["ukazhite_nomera_telefonov_do_10_nomerov"] == ["375292222222"]

    by_id = {item.message_id: item.external_id for item in response.messages}
    assert by_id[existing_id] == "sid-old"
    assert by_id[new_id] == "sid-new"
