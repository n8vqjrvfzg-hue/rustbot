"""К каждому новому сообщению бота в личке добавляется кнопка «🏠 Главное меню»."""
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Если в клавиатуре уже есть выход в меню (или это само меню), кнопку не добавляем
SKIP_CALLBACKS = {"menu", "home", "profile", "apply", "tut:0"}


class HomeButtonMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        if isinstance(method, SendMessage) and isinstance(method.chat_id, int) and method.chat_id > 0:
            markup = method.reply_markup
            if markup is None or isinstance(markup, InlineKeyboardMarkup):
                rows = [list(row) for row in (markup.inline_keyboard if markup else [])]
                if not any(b.callback_data in SKIP_CALLBACKS for row in rows for b in row):
                    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")])
                    method = method.model_copy(update={"reply_markup": InlineKeyboardMarkup(inline_keyboard=rows)})
        return await make_request(bot, method)
