from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

from keyboards.admin import user_label


def rep_menu_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="👍 Дать репутацию", callback_data="rep:find:vote")],
        [Btn(text="🏆 Топ репутации", callback_data="rep:top")],
        [Btn(text="🚨 Пожаловаться", callback_data="rep:find:report")],
        [Btn(text="⬅️ Назад", callback_data="menu")],
    ])


def back_to_rep() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="⬅️ Назад", callback_data="rep")]])


def cancel_rep() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="rep")]])


def pick_kb(users, mode: str) -> Kb:
    rows = [[Btn(text=user_label(u), callback_data=f"rep:pick:{mode}:{u['tg_id']}")] for u in users]
    rows.append([Btn(text="⬅️ Назад", callback_data="rep")])
    return Kb(inline_keyboard=rows)


def vote_kb(tid: int) -> Kb:
    return Kb(inline_keyboard=[
        [
            Btn(text="👍 +rep", callback_data=f"rep:v:p:{tid}"),
            Btn(text="👎 -rep", callback_data=f"rep:v:m:{tid}"),
        ],
        [Btn(text="⬅️ Назад", callback_data="rep")],
    ])


def complaint_kb(cid: int) -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="⚠️ Выдать варн", callback_data=f"cmp:warn:{cid}"),
        Btn(text="🗑 Отклонить", callback_data=f"cmp:dismiss:{cid}"),
    ]])
