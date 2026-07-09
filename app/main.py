from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.openapi import OPENAPI_TAGS
from app.domains.auth.router import router as auth_router
from app.domains.mailing.routers.mailing_router import router as mailing_router
from app.domains.mailing.routers.templates_router import router as templates_router
from app.domains.mailing.routers.services_router import router as services_router
from app.domains.providers.router import router as providers_router
from app.domains.stats.router import router as stats_router


settings = get_settings()

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
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
)
app.include_router(api_v1_router)


@app.get("/")
def read_root():
    """Root endpoint."""
    return {"Hello": "World"}
