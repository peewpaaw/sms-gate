from collections.abc import Sequence
from datetime import date, datetime, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MessageStatus
from app.domains.mailing.models import Mailing, Message
from app.domains.providers.models import Provider
from app.domains.stats.schemas import MessageProviderStatsItem


class MessageStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def counts_by_day_provider_status(
        self,
        *,
        start_utc: datetime,
        end_utc_exclusive: datetime,
        timezone_name: str,
        provider_codes: Sequence[str] | None = None,
        statuses: Sequence[MessageStatus] | None = None,
    ) -> list[MessageProviderStatsItem]:
        local_day = func.date_trunc(
            "day",
            func.timezone(timezone_name, Message.created_at),
        )
        day_date = cast(local_day, Date).label("day_date")

        query = (
            select(
                day_date,
                Mailing.provider_code,
                func.max(Provider.name).label("provider_name"),
                Message.status,
                func.count().label("count"),
            )
            .select_from(Message)
            .join(Mailing, Mailing.id == Message.mailing_id)
            .outerjoin(Provider, Provider.code == Mailing.provider_code)
            .where(
                Message.created_at >= start_utc,
                Message.created_at < end_utc_exclusive,
            )
            .group_by(day_date, Mailing.provider_code, Message.status)
            .order_by(day_date, Mailing.provider_code, Message.status)
        )

        if provider_codes:
            query = query.where(Mailing.provider_code.in_(provider_codes))
        if statuses:
            query = query.where(Message.status.in_(statuses))

        result = await self.session.execute(query)
        items: list[MessageProviderStatsItem] = []
        for row in result.all():
            items.append(
                MessageProviderStatsItem(
                    date=row.day_date,
                    provider_code=row.provider_code,
                    provider_name=row.provider_name,
                    status=row.status,
                    count=row.count,
                )
            )
        return items


def apply_fill_gaps(
    items: list[MessageProviderStatsItem],
    date_from: date,
    date_to: date,
) -> list[MessageProviderStatsItem]:
    if not items:
        return []

    keys: set[tuple[str, MessageStatus]] = set()
    names: dict[tuple[str, MessageStatus], str | None] = {}
    counts: dict[tuple[date, str, MessageStatus], int] = {}
    for item in items:
        key = (item.provider_code, item.status)
        keys.add(key)
        if key not in names or names[key] is None:
            names[key] = item.provider_name
        counts[(item.date, item.provider_code, item.status)] = item.count

    filled: list[MessageProviderStatsItem] = []
    current = date_from
    while current <= date_to:
        for provider_code, msg_status in sorted(keys, key=lambda k: (k[0], k[1].value)):
            filled.append(
                MessageProviderStatsItem(
                    date=current,
                    provider_code=provider_code,
                    provider_name=names.get((provider_code, msg_status)),
                    status=msg_status,
                    count=counts.get((current, provider_code, msg_status), 0),
                )
            )
        current += timedelta(days=1)
    return filled
