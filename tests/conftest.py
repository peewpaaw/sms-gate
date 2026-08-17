import base64
import secrets
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.domains.auth.enums import UserRole
from app.domains.auth.services import hash_password
from app.domains.mailing.enums import MailingStatus, MessageStatus
from app.domains.mailing.models import Mailing, Message
from app.main import app

API_PREFIX = "/api/v1"

_settings = get_settings()
_sync_engine = create_engine(
    _settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
)


def basic_auth_header(email: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _insert_user(
    *,
    email: str,
    password: str,
    role: UserRole,
    name: str = "pytest",
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    with _sync_engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO "user" (
                    id, is_active, password_hash, role, name, email, created_at, updated_at
                )
                VALUES (
                    :id, true, :password_hash, :role, :name, :email, :created_at, :updated_at
                )
                """
            ),
            {
                "id": uuid4(),
                "password_hash": hash_password(password),
                "role": role.value,
                "name": name,
                "email": email,
                "created_at": now,
                "updated_at": now,
            },
        )
        conn.commit()
    return basic_auth_header(email, password)


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
    password = secrets.token_urlsafe(16)
    email = f"pytest-{uuid4()}@example.com"
    return _insert_user(email=email, password=password, role=UserRole.USER)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    password = secrets.token_urlsafe(16)
    email = f"admin-{uuid4()}@example.com"
    return _insert_user(
        email=email, password=password, role=UserRole.ADMIN, name="admin"
    )


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
