from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.base import utcnow
from app.domains.auth.schemas import UserRead
from app.domains.mailing.models import MailingStatus, MessageStatus
from app.domains.providers.schemas import ProviderBrief


class MessageCreate(BaseModel):
    msisdn: str = Field(min_length=9, max_length=16)
    text: str = Field(min_length=1, max_length=1600)

    @field_validator("msisdn")
    @classmethod
    def normalize_msisdn(cls, value: str) -> str:
        """Normalize the msisdn to a string of digits and optional leading plus."""
        normalized = value.replace(" ", "").replace("+", "")
        if not normalized.isdigit():
            raise ValueError(
                "Msisdn must contain only digits and optional leading plus"
            )
        return normalized


class MailingCreate(BaseModel):
    provider_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    send_on: datetime = Field(default_factory=utcnow)
    messages: list[MessageCreate] = Field(default_factory=list)

    @field_validator("send_on", mode="before")
    @classmethod
    def default_send_on(cls, value: object) -> object:
        if value is None:
            return utcnow()
        return value


class MailingUpdate(BaseModel):
    provider_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    send_on: datetime = Field(default_factory=utcnow)
    messages: list[MessageCreate] | None = None

    @field_validator("send_on", mode="before")
    @classmethod
    def default_send_on(cls, value: object) -> object:
        if value is None:
            return utcnow()
        return value


class MessageUpdate(MessageCreate):
    """Full replace of one message fields (same as create)."""


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    msisdn: str
    text: str
    external_id: str | None
    status: MessageStatus
    batch_id: UUID | None = None


class MailingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    send_on: datetime
    provider_code: str
    provider: ProviderBrief
    status: MailingStatus
    messages: list[MessageRead]
    created_by: UserRead
    updated_by: UserRead
    created_at: datetime
    updated_at: datetime
