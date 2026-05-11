from uuid import UUID, uuid4

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ProviderDispatchStatus, enum_values


class ProviderDispatch(Base, TimestampMixin):
    __tablename__ = "provider_dispatches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("sms_batches.id"))
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("sms_messages.id"))
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ProviderDispatchStatus] = mapped_column(
        Enum(ProviderDispatchStatus, native_enum=False, values_callable=enum_values),
        default=ProviderDispatchStatus.CREATED,
        nullable=False,
    )
    request_hash: Mapped[str | None] = mapped_column(String(128))
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    error_payload: Mapped[dict | None] = mapped_column(JSON)
    raw_status: Mapped[str | None] = mapped_column(String(128))
    normalized_status: Mapped[str | None] = mapped_column(String(128))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    batch = relationship("SmsBatch", back_populates="dispatches")
