import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

import config
import ui
from database import db
from handlers.common import get_member
from keyboards.main import back_kb

router = Router()
log = logging.getLogger(__name__)


@router.callback_query(F.data == "composition")
async def show_composition(cb: CallbackQuery, bot: Bot):
    if not await get_member(cb):
        return

    try:
        channel_count = await bot.get_chat_member_count(config.CHANNEL)
    except Exception as e:
        log.warning("Не удалось получить число участников канала %s: %s", config.CHANNEL, e)
        channel_count = "недоступно"

    data = await db.composition()
    await cb.message.edit_text(ui.composition_text(data, channel_count), reply_markup=back_kb())
    await cb.answer()
