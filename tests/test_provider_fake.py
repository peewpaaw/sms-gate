from app.models.enums import SmsMessageStatus
from app.providers.base import ProviderBatch, ProviderMessage
from app.providers.fake import FakeSmsProviderAdapter


async def test_fake_provider_maps_response_by_custom_id():
    adapter = FakeSmsProviderAdapter()
    result = await adapter.send_batch(
        ProviderBatch(
            provider_code="fake",
            batch_id="batch-1",
            sender="ACME",
            messages=[
                ProviderMessage(
                    message_id="message-1",
                    custom_id="msg_123",
                    msisdn="375447222120",
                    text="hello",
                    sender="ACME",
                )
            ],
        )
    )

    assert result.accepted is True
    assert result.messages[0].message_id == "message-1"
    assert result.messages[0].provider_message_id == "fake_msg_123"
    assert result.messages[0].status == SmsMessageStatus.SUBMITTED
