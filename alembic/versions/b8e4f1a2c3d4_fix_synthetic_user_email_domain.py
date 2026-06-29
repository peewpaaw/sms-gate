"""fix synthetic user email domain

Revision ID: b8e4f1a2c3d4
Revises: 1209a6c16610
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4f1a2c3d4"
down_revision: Union[str, Sequence[str], None] = "1209a6c16610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET email = replace(email, '@internal.local', '@example.com')
            WHERE email LIKE '%@internal.local'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE "user"
            SET email = replace(email, '@example.com', '@internal.local')
            WHERE email LIKE '%@example.com'
              AND email ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}@example.com$'
            """
        )
    )
