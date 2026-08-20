from pydantic import BaseModel, ConfigDict

from app.domains.mailing.models import MailingStatus


class MailingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MailingStatus | None = None
    search: str | None = None
