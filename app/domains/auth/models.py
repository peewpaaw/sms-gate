from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampedMixin


class User(Base, TimestampedMixin):
    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
