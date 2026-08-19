from uuid import UUID

from pydantic import BaseModel


class SendBatchTask(BaseModel):
    mailing_id: UUID
    batch_id: UUID
    provider_code: str


class GetMessageStatusTask(BaseModel):
    message_id: UUID
    external_id: str
    provider_code: str
