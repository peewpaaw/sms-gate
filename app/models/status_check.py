from uuid import UUID, uuid4

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class StatusCheck(Base, TimestampMixin):
    __tablename__ = "status_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID | None] = mapped_column(ForeignKey("sms_messages.id"))
    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("sms_batches.id"))
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    raw_status: Mapped[str | None] = mapped_column(String(128))
    normalized_status: Mapped[str | None] = mapped_column(String(128))
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    error_payload: Mapped[dict | None] = mapped_column(JSON)
