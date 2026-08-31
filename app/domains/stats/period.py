from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_STATS_PERIOD_DAYS = 366


class InvalidTimezoneError(ValueError):
    pass


class InvalidStatsPeriodError(ValueError):
    pass


def resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezoneError(f"Unknown timezone: {tz_name!r}") from exc


def utc_bounds_for_inclusive_dates(
    date_from: date,
    date_to: date,
    tz_name: str,
) -> tuple[datetime, datetime]:
    if date_to < date_from:
        raise InvalidStatsPeriodError("date_to must be on or after date_from")

    period_days = (date_to - date_from).days + 1
    if period_days > MAX_STATS_PERIOD_DAYS:
        raise InvalidStatsPeriodError(
            f"Period must not exceed {MAX_STATS_PERIOD_DAYS} days"
        )

    tz = resolve_timezone(tz_name)
    start_local = datetime.combine(date_from, time.min, tzinfo=tz)
    end_local_exclusive = datetime.combine(
        date_to + timedelta(days=1), time.min, tzinfo=tz
    )
    return (
        start_local.astimezone(timezone.utc),
        end_local_exclusive.astimezone(timezone.utc),
    )
