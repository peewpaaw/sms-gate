"""fix_messages_batch_naming

Revision ID: 29af69ebc6fd
Revises: 2534495eb229
Create Date: 2026-05-15 13:04:42.085959

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '29af69ebc6fd'
down_revision: Union[str, Sequence[str], None] = '2534495eb229'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("message_batch", "messages_batch")


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table("messages_batch", "message_batch")
