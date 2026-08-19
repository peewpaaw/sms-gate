"""Pytest fixtures. Uses a dedicated DB so tests never touch the app database.

Override with env `TEST_DATABASE_URL` if needed. Default: `.../smsgate_test`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

# Must run before any app.* import — session engine binds URL at import time.
_DEFAULT_TEST_DB_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/smsgate_test"
)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB_URL)

import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.db.session import async_session_factory, engine
from app.domains.auth.services import hash_api_key
from app.domains.mailing.enums import MailingStatus, MessageStatus
from app.domains.mailing.models import Mailing, Message
from app.main import app

API_PREFIX = "/api/v1"
_ROOT = Path(__file__).resolve().parents[1]

_settings_url = os.environ["DATABASE_URL"]
_sync_url = _settings_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
_sync_engine = create_engine(_sync_url, isolation_level="AUTOCOMMIT")


def _admin_sync_url() -> str:
    """URL to the maintenance DB used to CREATE DATABASE."""
    # .../smsgate_test -> .../postgres
    if "/" not in _sync_url.rsplit("@", 1)[-1]:
        raise RuntimeError(f"Unexpected DATABASE_URL: {_settings_url}")
    base, _dbname = _sync_url.rsplit("/", 1)
    return f"{base}/postgres"


def _test_db_name() -> str:
    return _sync_url.rsplit("/", 1)[-1]


def _ensure_test_database() -> None:
    db_name = _test_db_name()
    admin_engine = create_engine(_admin_sync_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def _alembic_upgrade() -> None:
    env = {**os.environ, "DATABASE_URL": _settings_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_ROOT,
        env=env,
        check=True,
    )


def _reseed_providers(conn) -> None:
    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            INSERT INTO provider (code, name, is_enabled, created_at, updated_at)
            VALUES
                ('fake', 'Fake (dev)', true, :now, :now),
                ('beltelecom', 'Белтелеком', true, :now, :now)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"now": now},
    )


def _truncate_data_tables() -> None:
    with _sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename <> 'alembic_version'
                """
            )
        ).scalars()
        tables = list(rows)
        if not tables:
            return
        quoted = ", ".join(f'"{t}"' for t in tables)
        conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
        _reseed_providers(conn)


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> Iterator[None]:
    _ensure_test_database()
    _alembic_upgrade()
    yield
    _sync_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    _truncate_data_tables()
    yield


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

    return {"X-API-Key": api_key}


@pytest.fixture
def mailing_payload() -> Callable[..., dict]:
    def _factory(**overrides: object) -> dict:
        payload: dict = {
            "provider_code": "fake",
            "name": "test mailing",
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
