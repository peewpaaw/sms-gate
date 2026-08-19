"""Widen outbox.event_type for mailing.status

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-08-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "outbox",
        "event_type",
        existing_type=sa.Enum(
            "mailing.send",
            name="outboxeventtype",
            native_enum=False,
        ),
        type_=sa.Enum(
            "mailing.send",
            "mailing.status",
            name="outboxeventtype",
            native_enum=False,
            length=32,
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "outbox",
        "event_type",
        existing_type=sa.Enum(
            "mailing.send",
            "mailing.status",
            name="outboxeventtype",
            native_enum=False,
            length=32,
        ),
        type_=sa.Enum(
            "mailing.send",
            name="outboxeventtype",
            native_enum=False,
        ),
        existing_nullable=False,
    )
