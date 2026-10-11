from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

import calendar

import timeutil
from ui import MONTHS


def _shift(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def calendar_kb(year: int, month: int, events) -> Kb:
    days = {timeutil.to_local(e["starts_at"]).day for e in events}
    now = timeutil.local_now()
    today = now.day if (now.year, now.month) == (year, month) else None
    py, pm = _shift(year, month, -1)
    ny, nm = _shift(year, month, 1)

    rows = [
        [
            Btn(text="◀️", callback_data=f"ev:cal:{py}-{pm:02d}"),
            Btn(text=f"{MONTHS[month - 1]} {year}", callback_data="ev:noop"),
            Btn(text="▶️", callback_data=f"ev:cal:{ny}-{nm:02d}"),
        ],
        [Btn(text=w, callback_data="ev:noop") for w in timeutil.WEEKDAYS],
    ]
    for week in calendar.monthcalendar(year, month):
        row = []
        for d in week:
            if d == 0:
                row.append(Btn(text="\u2800", callback_data="ev:noop"))
            elif d in days:
                row.append(Btn(text=f"🔥{d}", callback_data=f"ev:day:{year}-{month:02d}-{d:02d}"))
            elif d == today:
                row.append(Btn(text=f"🔹{d}", callback_data="ev:noday"))
            else:
                row.append(Btn(text=str(d), callback_data="ev:noday"))
        rows.append(row)
    for e in events[:8]:
        rows.append([Btn(
            text=f"📌 {e['title'][:28]} · {timeutil.fmt_short(e['starts_at'])}",
            callback_data=f"ev:open:{e['id']}",
        )])
    rows.append([
        Btn(text="📍 Сегодня", callback_data="events"),
        Btn(text="⬅️ Назад", callback_data="menu"),
    ])
    return Kb(inline_keyboard=rows)


def event_kb(eid: int, i_go: bool, ym: str) -> Kb:
    toggle = "❌ Передумал" if i_go else "✅ Я пойду"
    return Kb(inline_keyboard=[
        [Btn(text=toggle, callback_data=f"ev:go:{eid}")],
        [Btn(text="⬅️ К календарю", callback_data=f"ev:cal:{ym}")],
    ])


def announce_kb(eid: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="📅 Подробнее", callback_data=f"ev:open:{eid}")]])


# ---------- админ ----------

def events_admin_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="➕ Создать мероприятие", callback_data="adm:ev:new")],
        [Btn(text="📋 Ближайшие мероприятия", callback_data="adm:ev:list")],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


def cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="adm:events")]])


def publish_kb() -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="✅ Опубликовать", callback_data="adm:ev:pub"),
        Btn(text="❌ Отмена", callback_data="adm:ev:cancel"),
    ]])


def admin_list_kb(events) -> Kb:
    rows = [
        [Btn(text=f"📌 {e['title'][:28]} · {timeutil.fmt_short(e['starts_at'])}", callback_data=f"adm:ev:view:{e['id']}")]
        for e in events
    ]
    rows.append([Btn(text="⬅️ Назад", callback_data="adm:events")])
    return Kb(inline_keyboard=rows)


def admin_event_kb(eid: int) -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="🗑 Удалить", callback_data=f"adm:ev:ask:{eid}")],
        [Btn(text="⬅️ К списку", callback_data="adm:ev:list")],
    ])


def confirm_delete_kb(eid: int) -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="✅ Да, удалить", callback_data=f"adm:ev:del:{eid}"),
        Btn(text="❌ Отмена", callback_data=f"adm:ev:view:{eid}"),
    ]])


def day_kb(events, year: int, month: int) -> Kb:
    rows = [
        [Btn(text=f"📌 {e['title'][:28]} · {timeutil.fmt_short(e['starts_at'])}", callback_data=f"ev:open:{e['id']}")]
        for e in events
    ]
    rows.append([Btn(text="⬅️ К календарю", callback_data=f"ev:cal:{year}-{month:02d}")])
    return Kb(inline_keyboard=rows)
