from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

try:  # сообщения старше 48 часов Telegram отдаёт боту как «недоступные»
    from aiogram.types import InaccessibleMessage
except ImportError:  # pragma: no cover
    InaccessibleMessage = ()

import roles
import ui
from database import db

# Кнопки, которые работают, даже если сообщение с ними уже устарело
STALE_OK = ("team:join:", "em:ack:", "em:noop", "menu", "home")


class AccessMiddleware(BaseMiddleware):
    """Устаревшие кнопки, бан и режим тех. работ. Администрация (админ и выше) проходит всегда."""

    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery) and (event.message is None or isinstance(event.message, InaccessibleMessage)):
            if not (event.data or "").startswith(STALE_OK):
                await event.answer("Это сообщение устарело. Открой меню командой /start.", show_alert=True)
                return

        user = data.get("event_from_user")
        chat = data.get("event_chat")

        # группы (админ-чат) не трогаем
        if user is None or (chat and chat.type != "private"):
            return await handler(event, data)

        row = await db.get_user(user.id)
        if row and roles.level(row["role"]) >= 2:
            return await handler(event, data)

        if row and row["status"] in ("banned", "blacklisted"):
            return

        if await db.get_setting("maintenance") == "1":
            if isinstance(event, CallbackQuery):
                await event.answer("🛠 Идут технические работы. Загляни чуть позже.", show_alert=True)
            else:
                await event.answer(ui.maintenance_text())
            return

        return await handler(event, data)
