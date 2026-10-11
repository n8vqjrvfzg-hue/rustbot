from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Kb

NOTIFY_LABELS = {
    "events": "Мероприятия",
    "votes": "Голосования",
    "emergency": "Экстренные сборы",
    "team": "Поиск команды",
}


def profile_kb() -> Kb:
    return Kb(inline_keyboard=[
        [
            Btn(text="✏️ Изменить ник", callback_data="profile:nick"),
            Btn(text="🎯 Игровые роли", callback_data="grole"),
        ],
        [
            Btn(text="🕒 Прайм-тайм", callback_data="prime"),
            Btn(text="🎮 Steam и часы", callback_data="steam"),
        ],
        [Btn(text="🔔 Уведомления", callback_data="notif")],
        [Btn(text="⬅️ Назад", callback_data="menu")],
    ])


def notif_kb(user) -> Kb:
    rows = []
    for key, label in NOTIFY_LABELS.items():
        on = user[f"notify_{key}"]
        rows.append([Btn(text=f"{'🔔' if on else '🔕'}  {label}", callback_data=f"notif:{key}")])
    rows.append([Btn(text="⬅️ Назад", callback_data="profile")])
    return Kb(inline_keyboard=rows)
