from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.providers.models import Provider


class ProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, *, enabled_only: bool = True) -> Sequence[Provider]:
        query = select(Provider).order_by(Provider.code)
        if enabled_only:
            query = query.where(Provider.is_enabled.is_(True))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_code(self, code: str) -> Provider | None:
        result = await self.session.execute(
            select(Provider).where(Provider.code == code)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        code: str,
        *,
        name: str | None = None,
        is_enabled: bool | None = None,
    ) -> Provider | None:
        provider = await self.get_by_code(code)
        if provider is None:
            return None

        if name is not None:
            provider.name = name
        if is_enabled is not None:
            provider.is_enabled = is_enabled

        await self.session.commit()
        await self.session.refresh(provider)
        return provider
