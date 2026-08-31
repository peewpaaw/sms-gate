from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.domains.auth.schemas import UserRead


class MailingTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=1600)


class MailingTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    text: str | None = Field(default=None, min_length=1, max_length=1600)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "MailingTemplateUpdate":
        if self.name is None and self.text is None:
            raise ValueError("At least one of name or text must be provided")
        return self


class MailingTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    text: str
    created_by: UserRead
    updated_by: UserRead
    created_at: datetime
    updated_at: datetime
