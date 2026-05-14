from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampedMixin
from .enums import MailingStatus, MessageStatus


class Mailing(Base, TimestampedMixin):
    __tablename__ = "mailing"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
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
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])


class Message(Base, TimestampedMixin):
    __tablename__ = "message"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailing_id: Mapped[UUID] = mapped_column(
        ForeignKey("mailing.id", ondelete="CASCADE"), nullable=False
    )
    msisdn: Mapped[str] = mapped_column(String(15), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(
            MessageStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MessageStatus.CREATED,
        nullable=False,
    )
    mailing = relationship("Mailing", back_populates="messages")
