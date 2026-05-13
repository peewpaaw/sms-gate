from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.domains.auth.models import User
from app.domains.auth.services import hash_api_key
from app.core.config import get_settings


settings = get_settings()

SessionDep = Annotated[AsyncSession, Depends(db_session.get_session)]


async def get_current_user(
    session: SessionDep, x_api_key: Annotated[str, Header(alias="X-API-Key")]
) -> User:

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    api_key_hash = hash_api_key(x_api_key)
    user = await session.scalar(select(User).where(User.api_key_hash == api_key_hash))

    if user is None and x_api_key == settings.default_api_key:
        user = User(api_key_hash=hash_api_key(x_api_key))
        session.add(user)
        await session.flush()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
