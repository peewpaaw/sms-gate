import secrets
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.domains.auth.services import hash_api_key
from app.domains.mailing.enums import MailingStatus, MessageStatus
from app.domains.mailing.models import Mailing, Message
from app.main import app

API_PREFIX = "/api/v1"

_settings = get_settings()
_sync_engine = create_engine(
    _settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
)


@pytest.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncIterator[None]:
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    api_key = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _sync_engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO "user" (
                    id, is_active, api_key_hash, name, email, created_at, updated_at
                )
                VALUES (
                    :id, true, :api_key_hash, :name, :email, :created_at, :updated_at
                )
                """
            ),
            {
                "id": uuid4(),
                "api_key_hash": hash_api_key(api_key),
                "name": "pytest",
                "email": f"pytest-{uuid4()}@example.com",
                "created_at": now,
                "updated_at": now,
            },
        )
        conn.commit()

    return {"X-API-Key": api_key}


@pytest.fixture
def mailing_payload() -> Callable[..., dict]:
    def _factory(**overrides: object) -> dict:
        payload: dict = {
            "provider_code": "fake",
            "messages": [
                {"msisdn": "375291234567", "text": "test message"},
            ],
        }
        payload.update(overrides)
        return payload

    return _factory


async def set_mailing_status(mailing_id: UUID, status: MailingStatus) -> None:
    async with async_session_factory() as session:
        mailing = await session.get(Mailing, mailing_id)
        assert mailing is not None
        mailing.status = status
        await session.commit()


async def set_message_status(message_id: UUID, status: MessageStatus) -> None:
    async with async_session_factory() as session:
        message = await session.get(Message, message_id)
        assert message is not None
        message.status = status
        await session.commit()
