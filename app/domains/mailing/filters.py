from pydantic import BaseModel, ConfigDict
from .models import MailingStatus


class MailingFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MailingStatus | None = None
