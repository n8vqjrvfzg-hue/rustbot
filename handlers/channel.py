"""Закрытый канал: участник получает личную одноразовую ссылку-приглашение."""
import logging
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import config
from handlers.common import get_member

router = Router()
log = logging.getLogger(__name__)


@router.callback_query(F.data == "channel")
async def channel_link(cb: CallbackQuery, bot: Bot):
    if not await get_member(cb):
        return
    try:
        link = await bot.create_chat_invite_link(
            config.CHANNEL,
            member_limit=1,                      # ссылка работает для одного человека
            expire_date=int(time.time()) + 3600,  # и живёт 1 час
        )
    except Exception as e:
        log.error("Не удалось создать ссылку на канал: %s", e)
        return await cb.answer("Не удалось создать ссылку. Сообщи администрации.", show_alert=True)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📣 Перейти в канал", url=link.invite_link)]])
    await cb.message.answer(
        "📣 <b>Твоя личная ссылка на канал</b>\n\nОна одноразовая и действует 1 час. Не передавай её другим.",
        reply_markup=markup,
    )
    await cb.answer()
