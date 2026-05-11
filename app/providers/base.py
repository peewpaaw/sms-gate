from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import SmsMessageStatus


class ProviderTemporaryError(Exception):
    pass


class ProviderPermanentError(Exception):
    pass


@dataclass(frozen=True)
class ProviderMessage:
    message_id: str
    custom_id: str
    msisdn: str
    text: str
    sender: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderBatch:
    provider_code: str
    batch_id: str
    sender: str
    messages: list[ProviderMessage]


@dataclass(frozen=True)
class ProviderMessageSendResult:
    message_id: str
    provider_message_id: str | None
    status: SmsMessageStatus
    raw_status: str | None = None
    price: int | None = None
    parts: int | None = None
    amount: int | None = None
    raw_item: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderSendResult:
    accepted: bool
    provider_batch_id: str | None
    messages: list[ProviderMessageSendResult]
    raw_response: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderStatusResult:
    provider_message_id: str
    status: SmsMessageStatus
    raw_status: str | None = None
    raw_response: dict = field(default_factory=dict)


class SmsProviderAdapter(Protocol):
    code: str
    max_batch_size: int

    async def send_batch(self, batch: ProviderBatch) -> ProviderSendResult: ...

    async def get_message_status(self, provider_message_id: str) -> ProviderStatusResult: ...
