from fastapi import FastAPI

from app.api.routes import health, mailings, messages, providers
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings)

app = FastAPI(title=settings.app_name)
app.include_router(health.router)
app.include_router(providers.router)
app.include_router(mailings.router)
app.include_router(messages.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name}