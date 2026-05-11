from app.models.enums import SmsMessageStatus
from app.providers.base import (
    ProviderBatch,
    ProviderMessageSendResult,
    ProviderSendResult,
    ProviderStatusResult,
)


class FakeSmsProviderAdapter:
    code = "fake"
    max_batch_size = 500

    async def send_batch(self, batch: ProviderBatch) -> ProviderSendResult:
        results = [
            ProviderMessageSendResult(
                message_id=message.message_id,
                provider_message_id=f"fake_{message.custom_id}",
                status=SmsMessageStatus.SUBMITTED,
                raw_status="accepted",
                price=0,
                parts=1,
                amount=0,
                raw_item={
                    "message_id": f"fake_{message.custom_id}",
                    "custom_id": message.custom_id,
                    "status": "accepted",
                },
            )
            for message in batch.messages
        ]
        return ProviderSendResult(
            accepted=True,
            provider_batch_id=f"fake_batch_{batch.batch_id[:12]}",
            messages=results,
            raw_response={"status": True, "messages": [result.raw_item for result in results]},
        )

    async def get_message_status(self, provider_message_id: str) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider_message_id=provider_message_id,
            status=SmsMessageStatus.DELIVERED,
            raw_status="delivered",
            raw_response={"message_id": provider_message_id, "status": "delivered"},
        )
