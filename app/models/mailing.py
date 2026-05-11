from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MailingSource, MailingStatus, enum_values


class Mailing(Base, TimestampMixin):
    __tablename__ = "mailings"
    __table_args__ = (Index("ix_mailings_created_by_status", "created_by", "status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source: Mapped[MailingSource] = mapped_column(
        Enum(MailingSource, native_enum=False, values_callable=enum_values), nullable=False
    )
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sender: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[MailingStatus] = mapped_column(
        Enum(MailingStatus, native_enum=False, values_callable=enum_values),
        default=MailingStatus.CREATED,
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(default=0, nullable=False)

    created_by_user = relationship("User", back_populates="mailings")
    messages = relationship("SmsMessage", back_populates="mailing", cascade="all, delete-orphan")
    batches = relationship("SmsBatch", back_populates="mailing", cascade="all, delete-orphan")
