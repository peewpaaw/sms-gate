from fastapi import APIRouter


router = APIRouter(prefix="/mailings", tags=["mailings"])


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Health check endpoint."""
    return {"message": "pong"}
