from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb


def cancel_support() -> Kb:
    return Kb(inline_keyboard=[[Btn(text="❌ Отмена", callback_data="menu")]])


def user_reply_kb(ticket_id: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="✉️ Ответить", callback_data=f"support:reply:{ticket_id}")]])


def ticket_kb(ticket_id: int) -> Kb:
    return Kb(inline_keyboard=[[Btn(text="🔒 Закрыть обращение", callback_data=f"tk:close:{ticket_id}")]])
