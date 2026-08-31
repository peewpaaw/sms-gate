from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.enums import UserRole
from app.domains.auth.models import User
from app.domains.auth.schemas import UserCreate, UserUpdate
from app.domains.auth.services import hash_password


class LastAdminError(Exception):
    """Cannot demote or deactivate the last active admin."""


class EmailAlreadyExistsError(Exception):
    """User with this email already exists."""


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[User]:
        query = (
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def count_active_admins(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        return result.scalar_one()

    async def create(self, payload: UserCreate) -> User:
        if await self.get_by_email(payload.email) is not None:
            raise EmailAlreadyExistsError()

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            name=payload.name,
            role=payload.role,
            is_active=payload.is_active,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user_id: UUID, payload: UserUpdate) -> User | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None

        would_lose_admin = (
            user.role == UserRole.ADMIN
            and user.is_active
            and (
                (payload.role is not None and payload.role != UserRole.ADMIN)
                or (payload.is_active is False)
            )
        )
        if would_lose_admin and await self.count_active_admins() <= 1:
            raise LastAdminError()

        if payload.email is not None and payload.email != user.email:
            existing = await self.get_by_email(payload.email)
            if existing is not None:
                raise EmailAlreadyExistsError()
            user.email = payload.email

        if payload.password is not None:
            user.password_hash = hash_password(payload.password)
        if payload.name is not None:
            user.name = payload.name
        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active

        await self.session.commit()
        await self.session.refresh(user)
        return user
