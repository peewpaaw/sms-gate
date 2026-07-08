from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.auth.schemas import UserRead
from app.domains.mailing.enums import MessagesBatchStatus
from app.domains.mailing.models import MailingStatus, MessageStatus


class MessageCreate(BaseModel):
    msisdn: str = Field(min_length=9, max_length=16)
    text: str = Field(min_length=1, max_length=1600)
    send_on: datetime | None = None

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
    messages: list[MessageCreate] = Field(default_factory=list)


class MailingUpdate(BaseModel):
    provider_code: str = Field(min_length=1, max_length=100)
    messages: list[MessageCreate] | None = None


class MessageUpdate(MessageCreate):
    """Full replace of one message fields (same as create)."""


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    msisdn: str
    text: str
    send_on: datetime | None
    external_id: str | None
    status: MessageStatus
    batch_id: UUID | None = None


class MailingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: MailingStatus
    messages: list[MessageRead]
    created_by: UserRead
    updated_by: UserRead
    created_at: datetime
    updated_at: datetime


class MessagesBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_code: str
    status: MessagesBatchStatus


class SendBatchTask(BaseModel):
    mailing_id: UUID
    batch_id: UUID
    provider_code: str


class GetMessageStatusTask(BaseModel):
    message_id: UUID
    external_id: str
    provider_code: str


class MailingTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=1600)


class MailingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    text: str | None = Field(default=None, min_length=1, max_length=1600)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "MailingTemplateUpdate":
        if self.name is None and self.text is None:
            raise ValueError("At least one of name or text must be provided")
        return self


class MailingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    text: str
    created_by: UserRead
    updated_by: UserRead
    created_at: datetime
    updated_at: datetime
