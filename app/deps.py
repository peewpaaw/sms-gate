from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.domains.auth.enums import UserRole
from app.domains.auth.models import User
from app.domains.auth.services import (
    DUMMY_PASSWORD_HASH,
    verify_password,
)


SessionDep = Annotated[AsyncSession, Depends(db_session.get_session)]

security = HTTPBasic()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Basic"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> User:
    user = await session.scalar(
        select(User).where(User.email == credentials.username)
    )

    if user is None:
        verify_password(credentials.password, DUMMY_PASSWORD_HASH)
        raise _unauthorized()

    if not verify_password(credentials.password, user.password_hash):
        raise _unauthorized()

    if not user.is_active:
        raise _unauthorized()

    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )
    return current_user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentAdminDep = Annotated[User, Depends(get_current_admin)]
