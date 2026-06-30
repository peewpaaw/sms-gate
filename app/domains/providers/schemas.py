from pydantic import BaseModel, ConfigDict, Field


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    is_enabled: bool
    max_batch_size: int


class ProviderListResponse(BaseModel):
    items: list[ProviderRead]


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_enabled: bool | None = None
