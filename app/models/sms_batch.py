from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import SmsBatchStatus, enum_values


class SmsBatch(Base, TimestampMixin):
    __tablename__ = "sms_batches"
    __table_args__ = (Index("ix_sms_batches_mailing_status", "mailing_id", "status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailing_id: Mapped[UUID] = mapped_column(ForeignKey("mailings.id"), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_batch_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[SmsBatchStatus] = mapped_column(
        Enum(SmsBatchStatus, native_enum=False, values_callable=enum_values),
        default=SmsBatchStatus.CREATED,
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    mailing = relationship("Mailing", back_populates="batches")
    messages = relationship("SmsMessage", back_populates="batch")
    dispatches = relationship("ProviderDispatch", back_populates="batch")
