from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider


async def ensure_fake_provider(session: AsyncSession) -> Provider:
    provider = await session.scalar(select(Provider).where(Provider.code == "fake"))
    if provider is not None:
        return provider

    provider = Provider(
        code="fake",
        name="Fake SMS Provider",
        is_active=True,
        max_batch_size=500,
        capabilities={"custom_id": True, "status_polling": True},
        priority=100,
    )
    session.add(provider)
    await session.flush()
    return provider
