from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import SessionDep
from app.models.provider import Provider
from app.schemas.provider import ProviderRead
from app.services.seeding import ensure_fake_provider

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderRead])
async def list_providers(session: SessionDep) -> list[ProviderRead]:
    await ensure_fake_provider(session)
    await session.commit()
    providers = (
        await session.scalars(
            select(Provider).where(Provider.is_active.is_(True)).order_by(Provider.code)
        )
    ).all()
    return [
        ProviderRead(
            id=provider.id,
            code=provider.code,
            name=provider.name,
            is_active=provider.is_active,
            max_batch_size=provider.max_batch_size,
            capabilities=provider.capabilities,
        )
        for provider in providers
    ]
