from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.openapi import OPENAPI_TAGS
from app.domains.auth.enums import UserRole
from app.domains.auth.models import User
from app.domains.auth.services import hash_password
from app.domains.auth.users_router import router as users_router
from app.domains.mailing.routers.mailing_router import router as mailing_router
from app.domains.mailing.routers.templates_router import router as templates_router
from app.domains.mailing.routers.services_router import router as services_router
from app.domains.providers.router import router as providers_router
from app.domains.stats.router import router as stats_router


settings = get_settings()


async def bootstrap_admin() -> None:
    if not settings.admin_email or not settings.admin_password:
        return

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.admin_email)
        )
        if existing is not None:
            return

        session.add(
            User(
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                name="Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await bootstrap_admin()
    yield


api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(users_router)
api_v1_router.include_router(mailing_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(services_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(stats_router)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API шлюза SMS-рассылок.",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.include_router(api_v1_router)


@app.get("/")
def read_root():
    """Root endpoint."""
    return {"Hello": "World"}
