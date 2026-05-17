"""add_provider_message_id

Revision ID: 7b4f0e6a0d1c
Revises: 22fc26656ec8
Create Date: 2026-05-17 20:52:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b4f0e6a0d1c"
down_revision: Union[str, Sequence[str], None] = "22fc26656ec8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "message",
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("message", "provider_message_id")
