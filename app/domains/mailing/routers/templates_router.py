from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.pagination import Page
from app.deps import CurrentUserDep, SessionDep
from app.domains.mailing.repositories import MailingTemplateRepository
from app.domains.mailing.schemas import (
    MailingTemplateCreate,
    MailingTemplateRead,
    MailingTemplateUpdate,
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get(
    "/",
    summary="Список шаблонов",
    description="Пагинация по всем шаблонам.",
)
async def list_mailing_templates(
    session: SessionDep,
    _current_user: CurrentUserDep,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[MailingTemplateRead]:
    repository = MailingTemplateRepository(session)
    templates = await repository.list(limit=limit, offset=offset)
    total = await repository.count()
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[MailingTemplateRead.model_validate(t) for t in templates],
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Создать шаблон",
    description="Имя шаблона уникально в рамках пользователя.",
)
async def create_mailing_template(
    session: SessionDep,
    current_user: CurrentUserDep,
    payload: MailingTemplateCreate,
) -> MailingTemplateRead:
    repository = MailingTemplateRepository(session)
    template = await repository.create(payload, created_by_id=current_user.id)
    return MailingTemplateRead.model_validate(template)


@router.get(
    "/{template_id}",
    summary="Шаблон по ID",
)
async def get_mailing_template(
    session: SessionDep,
    _current_user: CurrentUserDep,
    template_id: UUID,
) -> MailingTemplateRead:
    repository = MailingTemplateRepository(session)
    template = await repository.get_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Mailing template not found")
    return MailingTemplateRead.model_validate(template)


@router.patch(
    "/{template_id}",
    summary="Обновить шаблон",
    description="Частичное обновление: нужно передать хотя бы одно из полей `name`, `text`.",
)
async def update_mailing_template(
    session: SessionDep,
    current_user: CurrentUserDep,
    template_id: UUID,
    payload: MailingTemplateUpdate,
) -> MailingTemplateRead:
    repository = MailingTemplateRepository(session)
    template = await repository.update(
        template_id, payload, updated_by_id=current_user.id
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Mailing template not found")
    return MailingTemplateRead.model_validate(template)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить шаблон",
)
async def delete_mailing_template(
    session: SessionDep,
    _current_user: CurrentUserDep,
    template_id: UUID,
) -> None:
    repository = MailingTemplateRepository(session)
    deleted = await repository.delete(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mailing template not found")
    await session.commit()
