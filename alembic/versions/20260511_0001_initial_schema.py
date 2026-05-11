"""initial schema

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260511_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("api_key_hash", sa.String(length=128), nullable=False),
        sa.Column("role", sa.Enum("ui", "erp", name="userrole", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("max_batch_size", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("credentials_ref", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_providers_code"), "providers", ["code"], unique=True)
    op.create_table(
        "mailings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("ui", "erp", name="mailingsource", native_enum=False),
            nullable=False,
        ),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "queued",
                "processing",
                "partially_submitted",
                "submitted",
                "partially_delivered",
                "delivered",
                "partially_failed",
                "failed",
                "cancelled",
                name="mailingstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mailings_created_by_status", "mailings", ["created_by", "status"])
    op.create_table(
        "sms_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailing_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_batch_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "queued",
                "sending",
                "submitted",
                "status_pending",
                "completed",
                "partially_failed",
                "failed",
                name="smsbatchstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mailing_id"], ["mailings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_batches_mailing_status", "sms_batches", ["mailing_id", "status"])
    op.create_index(op.f("ix_sms_batches_provider_batch_id"), "sms_batches", ["provider_batch_id"])
    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailing_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_custom_id", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("msisdn", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sender", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "queued",
                "sending",
                "submitted",
                "delivered",
                "undelivered",
                "failed",
                "unknown",
                name="smsmessagestatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("raw_provider_status", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["sms_batches.id"]),
        sa.ForeignKeyConstraint(["mailing_id"], ["mailings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_code",
            "provider_custom_id",
            name="uq_message_provider_custom_id",
        ),
    )
    op.create_index("ix_sms_messages_mailing_status", "sms_messages", ["mailing_id", "status"])
    op.create_index("ix_sms_messages_recipient", "sms_messages", ["msisdn"])
    op.create_index(
        op.f("ix_sms_messages_provider_message_id"),
        "sms_messages",
        ["provider_message_id"],
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
    )
    op.create_index("ix_idempotency_user_key", "idempotency_keys", ["user_id", "key"])
    op.create_table(
        "provider_dispatches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "created",
                "sent_to_provider",
                "accepted",
                "rejected",
                "temporary_error",
                "permanent_error",
                "retry_scheduled",
                "dead_lettered",
                name="providerdispatchstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("request_hash", sa.String(length=128), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.Column("raw_status", sa.String(length=128), nullable=True),
        sa.Column("normalized_status", sa.String(length=128), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["sms_batches.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["sms_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "status_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("raw_status", sa.String(length=128), nullable=True),
        sa.Column("normalized_status", sa.String(length=128), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["sms_batches.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["sms_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(
        sa.table(
            "providers",
            sa.column("id", sa.Uuid()),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("max_batch_size", sa.Integer),
            sa.column("capabilities", sa.JSON),
            sa.column("priority", sa.Integer),
            sa.column("credentials_ref", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "code": "fake",
                "name": "Fake SMS Provider",
                "is_active": True,
                "max_batch_size": 500,
                "capabilities": {"custom_id": True, "status_polling": True},
                "priority": 100,
                "credentials_ref": None,
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("status_checks")
    op.drop_table("provider_dispatches")
    op.drop_index("ix_idempotency_user_key", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    op.drop_index(op.f("ix_sms_messages_provider_message_id"), table_name="sms_messages")
    op.drop_index("ix_sms_messages_recipient", table_name="sms_messages")
    op.drop_index("ix_sms_messages_mailing_status", table_name="sms_messages")
    op.drop_table("sms_messages")
    op.drop_index(op.f("ix_sms_batches_provider_batch_id"), table_name="sms_batches")
    op.drop_index("ix_sms_batches_mailing_status", table_name="sms_batches")
    op.drop_table("sms_batches")
    op.drop_index("ix_mailings_created_by_status", table_name="mailings")
    op.drop_table("mailings")
    op.drop_index(op.f("ix_providers_code"), table_name="providers")
    op.drop_table("providers")
    op.drop_table("users")
