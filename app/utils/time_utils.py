"""
Cambodia time helpers — all display and day-boundary logic should use these.
Database columns stay in UTC (best practice); conversion happens here.
"""
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

ICT = ZoneInfo("Asia/Phnom_Penh")   # UTC+7, no DST


def cambodia_now() -> datetime:
    """Current datetime in Cambodia (ICT)."""
    return datetime.now(ICT)


def cambodia_today() -> date:
    """Current calendar date in Cambodia."""
    return cambodia_now().date()


def fmt_ict(dt: datetime | None) -> str:
    """
    Format any datetime as a Cambodia local-time string.
    Naive datetimes are assumed to be UTC.
    """
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ICT)
    return local.strftime("%d %b %Y  %H:%M ICT")
