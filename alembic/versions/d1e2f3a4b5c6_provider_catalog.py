"""provider catalog and FK from mailing

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "provider",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("is_enabled", sa.Boolean),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "code": "fake",
                "name": "Fake (dev)",
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "code": "beltelecom",
                "name": "Белтелеком",
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO provider (code, name, is_enabled, created_at, updated_at)
            SELECT DISTINCT m.provider_code, m.provider_code, true, :now, :now
            FROM mailing m
            WHERE m.provider_code NOT IN (SELECT code FROM provider)
            """
        ).bindparams(now=now)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO provider (code, name, is_enabled, created_at, updated_at)
            SELECT DISTINCT b.provider_code, b.provider_code, true, :now, :now
            FROM messages_batch b
            WHERE b.provider_code NOT IN (SELECT code FROM provider)
            """
        ).bindparams(now=now)
    )

    op.create_foreign_key(
        "fk_mailing_provider_code",
        "mailing",
        "provider",
        ["provider_code"],
        ["code"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_messages_batch_provider_code",
        "messages_batch",
        "provider",
        ["provider_code"],
        ["code"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_batch_provider_code", "messages_batch", type_="foreignkey")
    op.drop_constraint("fk_mailing_provider_code", "mailing", type_="foreignkey")
    op.drop_table("provider")
