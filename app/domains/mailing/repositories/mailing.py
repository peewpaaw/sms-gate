from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.domains.mailing.models import Mailing, MailingStatus
from app.domains.mailing.repositories.base import SqlAlchemyRepository


class MailingRepository(SqlAlchemyRepository[Mailing]):
    model_type = Mailing

    async def get_by_id(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.provider),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .where(Mailing.id == mailing_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_update(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.provider),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .where(Mailing.id == mailing_id)
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: MailingStatus | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Mailing]:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.provider),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .order_by(Mailing.created_at.desc())
        )
        query = self._apply_filters(query, status=status, search=search)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(
        self,
        *,
        status: MailingStatus | None = None,
        search: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(Mailing)
        query = self._apply_filters(query, status=status, search=search)
        result = await self._session.execute(query)
        return result.scalar_one()

    @staticmethod
    def _apply_filters(query, *, status: MailingStatus | None, search: str | None):
        if status is not None:
            query = query.where(Mailing.status == status)
        if search is not None and (term := search.strip()):
            query = query.where(Mailing.name.ilike(f"%{term}%"))
        return query
