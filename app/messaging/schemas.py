from uuid import UUID

from pydantic import BaseModel


class SendBatchTask(BaseModel):
    batch_id: UUID
    mailing_id: UUID
    provider_code: str
    correlation_id: str | None = None


class StatusCheckTask(BaseModel):
    message_id: UUID
    provider_code: str
    provider_message_id: str
    correlation_id: str | None = None
