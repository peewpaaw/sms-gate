from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampedMixin
from app.messaging.outbox.enums import OutboxEventType, OutboxStatus


class Outbox(Base, TimestampedMixin):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_status_next_retry_at", "status", "next_retry_at"),
        Index(
            "ix_outbox_pending_created_at",
            "created_at",
            postgresql_where=(f"status = '{OutboxStatus.PENDING.value}'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[OutboxEventType] = mapped_column(
        Enum(
            OutboxEventType,
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
