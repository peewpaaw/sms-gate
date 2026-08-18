from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Protocol

from .exceptions import (
    ProviderTemporaryError,
)


######################################
# DTO: PROVIDER INPUT - SEND MESSAGE #
######################################


@dataclass(frozen=True)
class ProviderMessage:
    """One message in batch"""

    message_id: UUID
    msisdn: str
    text: str
    send_on: datetime | None
    external_id: str | None = None


@dataclass(frozen=True)
class ProviderBatch:
    """Batch of messages to send"""

    messages: list[ProviderMessage]


#######################################
# DTO: PROVIDER OUTPUT - SEND MESSAGE #
#######################################


@dataclass(frozen=True)
class ProviderOneMessageSendResponse:
    """Response from provider (one message in batch)"""

    message_id: UUID
    external_id: str


@dataclass(frozen=True)
class ProviderSendResponse:
    """Response from provider after sending batch"""

    status: bool
    messages: list[ProviderOneMessageSendResponse]


#####################################
# DTO: PROVIDER OUTPUT - GET STATUS #
#####################################


@dataclass(frozen=True)
class ProviderOneMessageStatusResponse:
    """Status of one message"""

    # TODO: при батче Белтелекома нет message_id. Один SID на несколько номеров.
    # => идентификация только по msisdn + общий не несколько msisnd sid
    message_id: UUID | None
    msisdn: str | None
    code: str
    name: str

    def __post_init__(self) -> None:
        if self.message_id is None and self.msisdn is None:
            raise ProviderTemporaryError("Message ID and phone number are missing")


@dataclass(frozen=True)
class ProviderStatusResponse:
    """Status of batch"""

    status: str
    messages_status: list[ProviderOneMessageStatusResponse]


#####################
# PROVIDER PROTOCOL #
#####################


class Provider(Protocol):
    """Provider interface"""

    code: str
    max_batch_size: int

    async def send(self, batch: ProviderBatch) -> ProviderSendResponse: ...

    async def get_status(self, external_id: str) -> ProviderStatusResponse: ...
