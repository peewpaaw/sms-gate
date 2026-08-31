from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUserDep, SessionDep, owner_scope
from app.domains.mailing.enums import MessageStatus
from app.domains.stats.period import (
    InvalidStatsPeriodError,
    InvalidTimezoneError,
    utc_bounds_for_inclusive_dates,
)
from app.domains.stats.repositories import MessageStatsRepository, apply_fill_gaps
from app.domains.stats.schemas import MessageProviderStatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/messages-by-provider",
    summary="Статистика сообщений по провайдерам",
    description=(
        "Агрегация числа message по календарным дням (день по message.created_at "
        "в указанной timezone), провайдеру (mailing.provider_code) и status. "
        "date_from и date_to — inclusive календарные даты в timezone; фильтр по "
        "created_at: от начала date_from до конца date_to включительно."
    ),
)
async def message_stats_by_provider(
    session: SessionDep,
    current_user: CurrentUserDep,
    date_from: date = Query(description="Начало периода (inclusive), календарная дата."),
    date_to: date = Query(description="Конец периода (inclusive), календарная дата."),
    timezone: str = Query(
        default="UTC",
        description="IANA timezone для границ периода и группировки по дням.",
    ),
    provider_code: list[str] | None = Query(
        default=None,
        description="Фильтр по кодам провайдеров; можно повторить параметр.",
    ),
    status: list[MessageStatus] | None = Query(
        default=None,
        description="Фильтр по статусам message; можно повторить параметр.",
    ),
    fill_gaps: bool = Query(
        default=False,
        description=(
            "Добавить count=0 для каждого дня периода и каждой пары "
            "(provider_code, status), встречавшейся в выборке."
        ),
    ),
) -> MessageProviderStatsResponse:
    try:
        start_utc, end_utc = utc_bounds_for_inclusive_dates(
            date_from, date_to, timezone
        )
    except InvalidTimezoneError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidStatsPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    repository = MessageStatsRepository(session)
    items = await repository.counts_by_day_provider_status(
        start_utc=start_utc,
        end_utc_exclusive=end_utc,
        timezone_name=timezone,
        provider_codes=provider_code,
        statuses=status,
        created_by_id=owner_scope(current_user),
    )

    if fill_gaps:
        items = apply_fill_gaps(items, date_from, date_to)

    return MessageProviderStatsResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        items=items,
    )
