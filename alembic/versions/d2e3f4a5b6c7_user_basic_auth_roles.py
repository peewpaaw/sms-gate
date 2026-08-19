"""user basic auth and roles

Revision ID: d2e3f4a5b6c7
Revises: c2d3e4f5a6b7
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Invalid hash: existing rows keep FK integrity but cannot authenticate.
_INVALID_PASSWORD_HASH = "!"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("role", sa.String(length=32), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE \"user\" SET password_hash = :hash, role = 'user' "
            "WHERE password_hash IS NULL"
        ).bindparams(hash=_INVALID_PASSWORD_HASH)
    )
    op.alter_column("user", "password_hash", nullable=False)
    op.alter_column("user", "role", nullable=False)
    op.drop_constraint("user_api_key_hash_key", "user", type_="unique")
    op.drop_column("user", "api_key_hash")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column("api_key_hash", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint("user_api_key_hash_key", "user", ["api_key_hash"])
    op.drop_column("user", "role")
    op.drop_column("user", "password_hash")
