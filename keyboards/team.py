from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb


def contact_url(u) -> str:
    return f"https://t.me/{u['username']}" if u["username"] else f"tg://user?id={u['tg_id']}"


def team_menu_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="➕ Подать заявку", callback_data="team:new")],
        [Btn(text="📋 Мои заявки", callback_data="team:my")],
        [Btn(text="⬅️ Назад", callback_data="menu")],
    ])


def cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="team")]])


def join_kb(rid: int, n: int) -> Kb:
    label = f"✋ Я готов ({n})" if n else "✋ Я готов"
    return Kb(inline_keyboard=[[Btn(text=label, callback_data=f"team:join:{rid}")]])


def contact_kb(u) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="💬 Написать", url=contact_url(u))]])


def my_requests_kb(reqs, counts: dict) -> Kb:
    rows = [
        [Btn(text=f"#{r['id']} · {r['text'][:28]} · ✋{counts.get(r['id'], 0)}", callback_data=f"team:view:{r['id']}")]
        for r in reqs
    ]
    rows.append([Btn(text="⬅️ Назад", callback_data="team")])
    return Kb(inline_keyboard=rows)


def request_view_kb(rid: int, responders) -> Kb:
    rows = [[Btn(text=f"💬 {(r['nick'] or r['name'] or r['tg_id'])}", url=contact_url(r))] for r in responders]
    rows.append([Btn(text="🔒 Закрыть набор", callback_data=f"team:close:{rid}")])
    rows.append([Btn(text="⬅️ К заявкам", callback_data="team:my")])
    return Kb(inline_keyboard=rows)
