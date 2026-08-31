"""Widen mailing.status for delivered/undelivered/failed

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "mailing",
        "status",
        existing_type=sa.Enum(
            "created",
            "queued",
            "submitted",
            name="mailingstatus",
            native_enum=False,
        ),
        type_=sa.Enum(
            "created",
            "queued",
            "submitted",
            "delivered",
            "undelivered",
            "failed",
            name="mailingstatus",
            native_enum=False,
            length=16,
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "mailing",
        "status",
        existing_type=sa.Enum(
            "created",
            "queued",
            "submitted",
            "delivered",
            "undelivered",
            "failed",
            name="mailingstatus",
            native_enum=False,
            length=16,
        ),
        type_=sa.Enum(
            "created",
            "queued",
            "submitted",
            name="mailingstatus",
            native_enum=False,
        ),
        existing_nullable=False,
    )
