from fastapi import APIRouter, FastAPI

from app.core.config import get_settings
from app.domains.mailing.router import router as mailing_router


settings = get_settings()

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(mailing_router)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(api_v1_router)


@app.get("/")
def read_root():
    """Root endpoint."""
    return {"Hello": "World"}
