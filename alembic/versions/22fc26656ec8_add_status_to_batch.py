"""add_status_to_batch

Revision ID: 22fc26656ec8
Revises: 29af69ebc6fd
Create Date: 2026-05-15 13:12:30.302260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22fc26656ec8'
down_revision: Union[str, Sequence[str], None] = '29af69ebc6fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    status_enum = sa.Enum(
        "created",
        "queued",
        "sent",
        "completed",
        "partially_failed",
        "failed",
        name="messagesbatchstatus",
        native_enum=False,
    )
    op.add_column(
        "messages_batch",
        sa.Column(
            "status",
            status_enum,
            nullable=False,
            server_default=sa.text("'created'"),
        ),
    )
    op.alter_column("messages_batch", "status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("messages_batch", "status")
