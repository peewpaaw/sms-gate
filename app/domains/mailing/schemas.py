from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.auth.schemas import UserRead
from app.domains.mailing.enums import MessagesBatchStatus
from app.domains.mailing.models import MailingStatus, MessageStatus

from app.domains.providers.base.provider import Provider
from app.domains.providers.registry import provider_registry


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
    messages: list[MessageCreate]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    msisdn: str
    text: str
    send_on: datetime | None
    external_id: str | None
    status: MessageStatus
    batch_id: UUID


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
