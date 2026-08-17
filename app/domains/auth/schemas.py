from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.auth.enums import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    name: str
    email: EmailStr
    role: UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=255)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
