"""Время: в базе хранится UTC, пользователю показываем в часовом поясе из .env."""
import logging
import re
from datetime import datetime, timedelta, timezone

import config

log = logging.getLogger(__name__)

TZ_NAME = config.TIMEZONE
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TZ_NAME)
except Exception:
    log.warning("Часовой пояс %s не найден (pip install tzdata). Использую UTC+3.", TZ_NAME)
    TZ = timezone(timedelta(hours=3))

TZ_LABEL = "МСК" if TZ_NAME == "Europe/Moscow" else TZ_NAME

FMT = "%Y-%m-%d %H:%M:%S"
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(FMT)


def now_str() -> str:
    return to_str(now_utc())


def in_days(days: int) -> str:
    return to_str(now_utc() + timedelta(days=days))


def in_minutes(minutes: int) -> str:
    return to_str(now_utc() + timedelta(minutes=minutes))


def to_local(s: str) -> datetime:
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc).astimezone(TZ)


def local_now() -> datetime:
    return now_utc().astimezone(TZ)


def parse_local(text: str) -> str | None:
    """'12.10.2026 20:00' (по местному времени) -> строка UTC."""
    try:
        dt = datetime.strptime(text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    return to_str(dt.replace(tzinfo=TZ))


def fmt_short(s: str) -> str:
    return to_local(s).strftime("%d.%m %H:%M")


def month_bounds(year: int, month: int) -> tuple[str, str]:
    start = datetime(year, month, 1, tzinfo=TZ)
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return to_str(start), to_str(datetime(ny, nm, 1, tzinfo=TZ))


def time_left(s: str) -> str:
    delta = datetime.strptime(s, FMT).replace(tzinfo=timezone.utc) - now_utc()
    secs = int(delta.total_seconds())
    if secs <= 0:
        return "уже прошло"
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} д {h} ч"
    if h:
        return f"{h} ч {m} мин"
    return f"{max(m, 1)} мин"


def day_bounds(year: int, month: int, day: int) -> tuple[str, str]:
    start = datetime(year, month, day, tzinfo=TZ)
    return to_str(start), to_str(start + timedelta(days=1))


def parse_prime(text: str) -> str | None:
    """'19-23' / '19:00-23:30' / '22:00–02:00' -> '19:00–23:00'."""
    t = text.strip().replace("–", "-").replace("—", "-").replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?-(\d{1,2})(?::(\d{2}))?", t)
    if not m:
        return None
    h1, m1 = int(m.group(1)), int(m.group(2) or 0)
    h2, m2 = int(m.group(3)), int(m.group(4) or 0)
    if h2 == 24 and m2 == 0:
        h2 = 0
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59 or (h1, m1) == (h2, m2):
        return None
    return f"{h1:02d}:{m1:02d}–{h2:02d}:{m2:02d}"
