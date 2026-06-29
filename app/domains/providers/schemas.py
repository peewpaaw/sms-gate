from pydantic import BaseModel


class ProviderListResponse(BaseModel):
    items: list[str]
