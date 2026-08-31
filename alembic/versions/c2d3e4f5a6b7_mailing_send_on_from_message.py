"""mailing.send_on from message, drop message.send_on

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mailing",
        sa.Column("send_on", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE mailing
            SET send_on = COALESCE(
                (
                    SELECT MIN(message.send_on)
                    FROM message
                    WHERE message.mailing_id = mailing.id
                ),
                mailing.created_at
            )
            """
        )
    )
    op.alter_column(
        "mailing",
        "send_on",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column("message", "send_on")


def downgrade() -> None:
    op.add_column(
        "message",
        sa.Column("send_on", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE message
            SET send_on = mailing.send_on
            FROM mailing
            WHERE message.mailing_id = mailing.id
            """
        )
    )
    op.alter_column(
        "message",
        "send_on",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column("mailing", "send_on")
