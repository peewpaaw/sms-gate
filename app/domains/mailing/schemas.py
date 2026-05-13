from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.auth.schemas import UserRead
from app.domains.mailing.models import MailingStatus, MessageStatus


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
    messages: list[MessageCreate]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    msisdn: str
    text: str
    status: MessageStatus


class MailingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: MailingStatus
    messages: list[MessageRead]
    created_by: UserRead
    updated_by: UserRead
    created_at: datetime
    updated_at: datetime
