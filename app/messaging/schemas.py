from uuid import UUID
from pydantic import BaseModel


class SendBatchTask(BaseModel):
    mailing_id: UUID
    batch_id: UUID
    provider_code: str
