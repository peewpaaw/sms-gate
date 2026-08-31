from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.mailing.enums import MessagesBatchStatus


class MessagesBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_code: str
    status: MessagesBatchStatus


class SendBatchTask(BaseModel):
    mailing_id: UUID
    batch_id: UUID
    provider_code: str
