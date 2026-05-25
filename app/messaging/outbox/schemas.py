from pydantic import BaseModel
from app.messaging.outbox.enums import OutboxEventType


class OutboxCreate(BaseModel):
    event_type: OutboxEventType
    payload: dict