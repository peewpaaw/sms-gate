from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.domains.mailing.models import MailingTemplate
from app.domains.mailing.repositories.base import SqlAlchemyRepository


class MailingTemplateRepository(SqlAlchemyRepository[MailingTemplate]):
    model_type = MailingTemplate

    async def get_by_id(self, template_id: UUID) -> MailingTemplate | None:
        query = (
            select(MailingTemplate)
            .options(
                selectinload(MailingTemplate.created_by),
                selectinload(MailingTemplate.updated_by),
            )
            .where(MailingTemplate.id == template_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[MailingTemplate]:
        query = (
            select(MailingTemplate)
            .options(
                selectinload(MailingTemplate.created_by),
                selectinload(MailingTemplate.updated_by),
            )
            .order_by(MailingTemplate.created_at.desc())
        )
        query = self._apply_filters(query, search=search)
        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self, *, search: str | None = None) -> int:
        query = select(func.count()).select_from(MailingTemplate)
        query = self._apply_filters(query, search=search)
        result = await self._session.execute(query)
        return result.scalar_one()

    @staticmethod
    def _apply_filters(query, *, search: str | None):
        if search is not None and (term := search.strip()):
            pattern = f"%{term}%"
            query = query.where(
                or_(
                    MailingTemplate.name.ilike(pattern),
                    MailingTemplate.text.ilike(pattern),
                )
            )
        return query
