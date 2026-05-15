import uuid
from .base.provider import (
    ProviderBatch,
    ProviderOneMessageSendResponse,
    ProviderSendResponse,
)


class FakeProvider:
    code = "fake"
    max_batch_size = 10

    async def send(self, batch: ProviderBatch) -> ProviderSendResponse:
        results = [
            ProviderOneMessageSendResponse(
                message_id=message.message_id,
                external_id=str(uuid.uuid4()),
            )
            for message in batch.messages
        ]

        return ProviderSendResponse(status=True, messages=results)
