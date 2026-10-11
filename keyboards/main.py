from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

import config


def channel_button() -> Btn:
    """Канал показывается только полноценным участникам."""
    if config.CHANNEL_URL:
        return Btn(text="📣 Наш канал", url=config.CHANNEL_URL)
    return Btn(text="📣 Наш канал", callback_data="channel")


def guest_menu() -> Kb:
    return Kb(inline_keyboard=[
        [Btn(text="📝 Заполнить анкету", callback_data="apply")],
    ])


def main_menu(level: int) -> Kb:
    rows = [
        [
            Btn(text="👤 Профиль", callback_data="profile"),
            Btn(text="📊 Состав", callback_data="composition"),
        ],
        [
            Btn(text="⭐ Репутация", callback_data="rep"),
            Btn(text="✉️ Написать админам", callback_data="support"),
        ],
        [
            Btn(text="📅 Мероприятия", callback_data="events"),
            Btn(text="🗳 Голосования", callback_data="polls"),
        ],
        [
            Btn(text="🔎 Поиск команды", callback_data="team"),
            Btn(text="📚 Факты о Rust", callback_data="facts"),
        ],
        [Btn(text="📜 Правила", callback_data="rules"), channel_button()],
    ]
    if level >= 1:
        rows.append([Btn(text="🛠 Админ-меню", callback_data="admin")])
    return Kb(inline_keyboard=rows)


def back_kb(target: str = "menu") -> Kb:
    return Kb(inline_keyboard=[[Btn(text="⬅️ Назад", callback_data=target)]])


def decision_kb(app_id: int) -> Kb:
    return Kb(inline_keyboard=[[
        Btn(text="✅ Принять", callback_data=f"app:accept:{app_id}"),
        Btn(text="❌ Отклонить", callback_data=f"app:reject:{app_id}"),
    ]])
