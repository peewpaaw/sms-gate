from uuid import UUID

from pydantic import BaseModel


class ProviderRead(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool
    max_batch_size: int
    capabilities: dict
