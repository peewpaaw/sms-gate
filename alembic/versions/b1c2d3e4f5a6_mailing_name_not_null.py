"""mailing.name not null

Revision ID: b1c2d3e4f5a6
Revises: a9b0c1d2e3f4
Create Date: 2026-08-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mailing",
        sa.Column("name", sa.String(length=255), nullable=True, server_default="unnamed"),
    )
    op.execute(sa.text("UPDATE mailing SET name = 'unnamed' WHERE name IS NULL"))
    op.alter_column(
        "mailing",
        "name",
        existing_type=sa.String(length=255),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("mailing", "name")
