from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.application.exceptions import TemplateNotFoundError
from app.domains.mailing.models import MailingTemplate
from app.domains.mailing.repositories import MailingTemplateRepository
from app.domains.mailing.schemas import MailingTemplateCreate, MailingTemplateUpdate


class TemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MailingTemplateRepository(session)

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MailingTemplate], int]:
        templates = list(await self._repo.list(limit=limit, offset=offset))
        total = await self._repo.count()
        return templates, total

    async def get(self, template_id: UUID) -> MailingTemplate:
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError
        return template

    async def create(
        self, payload: MailingTemplateCreate, created_by_id: UUID
    ) -> MailingTemplate:
        template = MailingTemplate(
            name=payload.name,
            text=payload.text,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        self._repo.add(template)
        await self._session.flush()
        created = await self._repo.get_by_id(template.id)
        assert created is not None
        return created

    async def update(
        self,
        template_id: UUID,
        payload: MailingTemplateUpdate,
        updated_by_id: UUID,
    ) -> MailingTemplate:
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError

        if payload.name is not None:
            template.name = payload.name
        if payload.text is not None:
            template.text = payload.text
        template.updated_by_id = updated_by_id

        await self._session.flush()
        updated = await self._repo.get_by_id(template_id)
        assert updated is not None
        return updated

    async def delete(self, template_id: UUID) -> None:
        template = await self._repo.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError

        await self._repo.delete(template)
        await self._session.flush()
