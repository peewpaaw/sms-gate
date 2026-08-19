from app.db.base import Base, TimestampedMixin
from app.domains.auth.models import User
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID, uuid4


class MailingTemplate(Base, TimestampedMixin):
    __tablename__ = "mailing_template"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )
    created_by = relationship(User, foreign_keys=[created_by_id])
    updated_by = relationship(User, foreign_keys=[updated_by_id])
