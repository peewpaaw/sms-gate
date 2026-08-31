from datetime import date

from pydantic import BaseModel, Field

from app.domains.mailing.enums import MessageStatus


class MessageProviderStatsItem(BaseModel):
    date: date
    provider_code: str
    provider_name: str | None = None
    status: MessageStatus
    count: int = Field(ge=0)


class MessageProviderStatsResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    items: list[MessageProviderStatsItem]
