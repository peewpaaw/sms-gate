import uuid

from app.domains.mailing.enums import MessageStatus

from .base.provider import (
    ProviderBatch,
    ProviderOneMessageSendResponse,
    ProviderOneMessageStatusResponse,
    ProviderSendResponse,
    ProviderStatusResponse,
)


class FakeProvider:
    code = "fake"
    max_batch_size = 1

    async def send(self, batch: ProviderBatch) -> ProviderSendResponse:
        results = [
            ProviderOneMessageSendResponse(
                message_id=message.message_id,
                external_id=str(uuid.uuid4()),
            )
            for message in batch.messages
        ]

        return ProviderSendResponse(status=True, messages=results)

    async def get_status(self, external_id: str) -> ProviderStatusResponse:
        return ProviderStatusResponse(
            status="delivered",
            messages_status=[
                ProviderOneMessageStatusResponse(
                    message_id=None,
                    msisdn=None,
                    status=MessageStatus.DELIVERED,
                )
            ],
        )
