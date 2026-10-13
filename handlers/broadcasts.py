"""Рассылка сообщений всем участникам (только для владельцев)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ui
from database import db
from keyboards.extras import cancel_kb
from utils import safe_edit, start_broadcast

router = Router()


class BroadcastState(StatesGroup):
    text = State()


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    """Владелец начинает рассылку."""
    level = await db.get_level(cb.from_user.id)
    if level < 5:  # только владелец
        return await cb.answer("Только владелец может отправлять рассылки.", show_alert=True)
    
    await state.set_state(BroadcastState.text)
    text = (
        f"{ui.header('📣', 'РАССЫЛКА ВСЕМ')}\\n\\n"
        "Отправь текст сообщения, которое получат все участники.\\n"
        "Можно использовать форматирование Telegram (жирный, курсив, ссылки).\\n\\n"
        "<i>Для отмены нажми «Отмена» или /start</i>"
    )
    await safe_edit(cb.message, text, cancel_kb())
    await cb.answer()


@router.message(BroadcastState.text, F.text)
async def broadcast_send(message: Message, state: FSMContext):
    """Владелец отправляет рассылку."""
    if await db.get_level(message.from_user.id) < 5:
        return await state.clear()
    
    text = message.html_text.strip()
    if len(text) < 10:
        return await message.answer("⚠️ Сообщение слишком короткое. Напиши что-нибудь подробнее.")
    
    # Создаём запись рассылки
    bid = await db.create_broadcast(message.from_user.id, text)
    users = await db._all("SELECT tg_id FROM users WHERE status = 'accepted'")
    
    await message.answer(
        f"📣 Рассылка создана\\n"
        f"Адресатов: {len(users)}\\n\\n"
        f"Отправляю... (может занять пару минут)"
    )
    
    await state.clear()
    
    # Отправляем в фоне
    async def send_all():
        ok = 0
        for user in users:
            try:
                await message.bot.send_message(user["tg_id"], text)
                ok += 1
            except Exception:
                pass
        await db.update_broadcast_stats(bid, ok, len(users))
    
    # Запуск в фоне через start_broadcast
    import asyncio
    asyncio.create_task(send_all())
