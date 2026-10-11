from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

import ui
from database import db


def polls_list_kb(polls, voted: set) -> Kb:
    rows = [
        [Btn(text=f"{'✅' if p['id'] in voted else '🗳'} {p['question'][:40]}", callback_data=f"pl:open:{p['id']}")]
        for p in polls
    ]
    rows.append([Btn(text="⬅️ Назад", callback_data="menu")])
    return Kb(inline_keyboard=rows)


def poll_kb(pid: int, options, can_vote: bool) -> Kb:
    rows = []
    if can_vote:
        rows = [
            [Btn(text=f"{ui.NUMS[i]} {opt[:40]}", callback_data=f"pl:v:{pid}:{i}")]
            for i, opt in enumerate(options)
        ]
    rows.append([Btn(text="⬅️ К голосованиям", callback_data="polls")])
    return Kb(inline_keyboard=rows)


def announce_kb(pid: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="🗳 Голосовать", callback_data=f"pl:open:{pid}")]])


# ---------- админ ----------

def polls_admin_kb() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="➕ Создать голосование", callback_data="adm:pl:new")],
        [Btn(text="📋 Все голосования", callback_data="adm:pl:list")],
        [Btn(text="⬅️ Назад", callback_data="admin")],
    ])


def cancel_kb() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="adm:polls")]])


def duration_kb() -> Kb:
    return Kb(inline_keyboard=[
        [
            Btn(text="1 день", callback_data="adm:pl:dur:1"),
            Btn(text="3 дня", callback_data="adm:pl:dur:3"),
        ],
        [
            Btn(text="7 дней", callback_data="adm:pl:dur:7"),
            Btn(text="♾ Без срока", callback_data="adm:pl:dur:0"),
        ],
        [Btn(text="❌ Отмена", callback_data="adm:polls")],
    ])


def admin_list_kb(polls) -> Kb:
    rows = [
        [Btn(
            text=f"{'🟢' if db.poll_is_open(p) else '🔒'} #{p['id']} {p['question'][:35]}",
            callback_data=f"adm:pl:view:{p['id']}",
        )]
        for p in polls
    ]
    rows.append([Btn(text="⬅️ Назад", callback_data="adm:polls")])
    return Kb(inline_keyboard=rows)


def admin_poll_kb(pid: int, is_open: bool) -> Kb:
    rows = []
    if is_open:
        rows.append([Btn(text="🔒 Завершить", callback_data=f"adm:pl:close:{pid}")])
    rows.append([Btn(text="🗑 Удалить", callback_data=f"adm:pl:ask:{pid}")])
    rows.append([Btn(text="⬅️ К списку", callback_data="adm:pl:list")])
    return Kb(inline_keyboard=rows)


def confirm_delete_kb(pid: int) -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="✅ Да, удалить", callback_data=f"adm:pl:del:{pid}"),
        Btn(text="❌ Отмена", callback_data=f"adm:pl:view:{pid}"),
    ]])
