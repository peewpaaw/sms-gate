from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
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
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(MailingTemplate)
        )
        return result.scalar_one()
