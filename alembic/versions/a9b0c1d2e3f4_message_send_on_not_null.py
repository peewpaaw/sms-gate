"""message.send_on default now, not null

Revision ID: a9b0c1d2e3f4
Revises: f1a2b3c4d5e6
Create Date: 2026-08-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE message SET send_on = created_at WHERE send_on IS NULL"))
    op.alter_column(
        "message",
        "send_on",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "message",
        "send_on",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
