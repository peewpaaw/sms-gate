from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domains.providers.base.provider import ProviderBatch, ProviderMessage
from app.domains.providers.beltelecom.provider import BeltelecomProvider


@pytest.mark.asyncio
async def test_beltelecom_send_passes_batch_name_in_payload() -> None:
    provider = BeltelecomProvider(
        base_url="https://example.test",
        username="user",
        password="pass",
    )
    provider._client.get_csrf_token = AsyncMock(return_value="csrf-token")
    provider._client.submit_sms = AsyncMock(return_value={"sid": "sid-1"})

    send_on = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    batch = ProviderBatch(
        name="campaign title",
        messages=[
            ProviderMessage(
                message_id=uuid4(),
                msisdn="375291234567",
                text="hello",
                send_on=send_on,
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
    assert payload["msisdn"] == "375291234567"
