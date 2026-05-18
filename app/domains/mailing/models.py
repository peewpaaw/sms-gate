from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampedMixin
from app.domains.auth.models import User
from .enums import MailingStatus, MessageStatus, MessagesBatchStatus


class Mailing(Base, TimestampedMixin):
    __tablename__ = "mailing"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[MailingStatus] = mapped_column(
        Enum(
            MailingStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MailingStatus.CREATED,
        nullable=False,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )

    messages = relationship(
        "Message", back_populates="mailing", cascade="all, delete-orphan"
    )
    batches = relationship(
        "MessagesBatch", back_populates="mailing", cascade="all, delete-orphan"
    )
    created_by = relationship(User, foreign_keys=[created_by_id])
    updated_by = relationship(User, foreign_keys=[updated_by_id])


class Message(Base, TimestampedMixin):
    __tablename__ = "message"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailing_id: Mapped[UUID] = mapped_column(
        ForeignKey("mailing.id", ondelete="CASCADE"), nullable=False
    )
    msisdn: Mapped[str] = mapped_column(String(15), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    send_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(
            MessageStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MessageStatus.CREATED,
        nullable=False,
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages_batch.id", ondelete="SET NULL"), nullable=True
    )

    mailing = relationship("Mailing", back_populates="messages")
    batch = relationship("MessagesBatch", back_populates="messages")


class MessagesBatch(Base, TimestampedMixin):
    __tablename__ = "messages_batch"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailing_id: Mapped[UUID] = mapped_column(
        ForeignKey("mailing.id", ondelete="CASCADE"), nullable=False
    )
    provider_code: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessagesBatchStatus] = mapped_column(
        Enum(
            MessagesBatchStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MessagesBatchStatus.CREATED,
        nullable=False,
    )
    messages_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    messages = relationship("Message", back_populates="batch")
    mailing = relationship("Mailing", back_populates="batches")
