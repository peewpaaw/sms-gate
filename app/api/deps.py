from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import hash_api_key

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    settings = get_settings()
    api_key = x_api_key or settings.default_user_api_key
    api_key_hash = hash_api_key(api_key)

    user = await session.scalar(select(User).where(User.api_key_hash == api_key_hash))
    if user is None and api_key in {settings.default_user_api_key, settings.erp_user_api_key}:
        role = UserRole.ERP if api_key == settings.erp_user_api_key else UserRole.UI
        user = User(
            email=f"{role.value}@local.sms-gate",
            api_key_hash=api_key_hash,
            role=role,
        )
        session.add(user)
        await session.flush()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
