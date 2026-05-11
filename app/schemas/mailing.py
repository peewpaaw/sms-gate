from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MailingStatus, SmsMessageStatus


class SmsMessageCreate(BaseModel):
    msisdn: str = Field(min_length=7, max_length=32)
    text: str = Field(min_length=1, max_length=1600)
    metadata: dict = Field(default_factory=dict)

    @field_validator("msisdn")
    @classmethod
    def normalize_msisdn(cls, value: str) -> str:
        normalized = value.strip().replace("+", "")
        if not normalized.isdigit():
            raise ValueError("msisdn must contain digits and optional leading plus")
        return normalized


class MailingCreate(BaseModel):
    provider_code: str = Field(min_length=1, max_length=64)
    sender: str = Field(min_length=1, max_length=64)
    messages: list[SmsMessageCreate] = Field(min_length=1, max_length=10_000)


class SmsMessageShort(BaseModel):
    message_id: UUID
    status: SmsMessageStatus


class MailingCreateResponse(BaseModel):
    mailing_id: UUID
    status: MailingStatus
    messages: list[SmsMessageShort]


class MailingRead(BaseModel):
    id: UUID
    provider_code: str
    sender: str
    status: MailingStatus
    message_count: int


class SmsMessageRead(BaseModel):
    id: UUID
    mailing_id: UUID
    batch_id: UUID | None
    provider_code: str
    provider_custom_id: str
    provider_message_id: str | None
    msisdn: str
    text: str
    sender: str
    status: SmsMessageStatus
    raw_provider_status: str | None
