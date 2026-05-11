from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import SmsMessageStatus, enum_values


class SmsMessage(Base, TimestampMixin):
    __tablename__ = "sms_messages"
    __table_args__ = (
        UniqueConstraint(
            "provider_code",
            "provider_custom_id",
            name="uq_message_provider_custom_id",
        ),
        Index("ix_sms_messages_mailing_status", "mailing_id", "status"),
        Index("ix_sms_messages_recipient", "msisdn"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailing_id: Mapped[UUID] = mapped_column(ForeignKey("mailings.id"), nullable=False)
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("sms_batches.id"))
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    msisdn: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SmsMessageStatus] = mapped_column(
        Enum(SmsMessageStatus, native_enum=False, values_callable=enum_values),
        default=SmsMessageStatus.CREATED,
        nullable=False,
    )
    raw_provider_status: Mapped[str | None] = mapped_column(String(128))

    mailing = relationship("Mailing", back_populates="messages")
    batch = relationship("SmsBatch", back_populates="messages")
