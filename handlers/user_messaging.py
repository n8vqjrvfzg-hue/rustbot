"""Отправка сообщений участникам от имени администрации (задача #3)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import ui
from database import db
from keyboards.extras import cancel_kb

router = Router()
MIN_LEVEL = 2  # админ и выше


class UserMessageState(StatesGroup):
    choose_user = State()
    type_message = State()


@router.callback_query(F.data == "adm:msg_user")
async def message_user_start(cb: CallbackQuery, state: FSMContext):
    """Админ начинает писать участнику."""
    level = await db.get_level(cb.from_user.id)
    if level < MIN_LEVEL:
        return await cb.answer("Недостаточно прав.", show_alert=True)
    
    await state.set_state(UserMessageState.choose_user)
    text = (
        f"{ui.header('✉️', 'НАПИСАТЬ УЧАСТНИКУ')}\n\n"
        "Отправь ID или никнейм участника (@username или числовой ID)."
    )
    await cb.message.edit_text(text, reply_markup=cancel_kb())
    await cb.answer()


@router.message(UserMessageState.choose_user, F.text)
async def message_user_choose(message: Message, state: FSMContext):
    """Админ указывает пользователя."""
    level = await db.get_level(message.from_user.id)
    if level < MIN_LEVEL:
        await state.clear()
        return
    
    user_input = message.text.strip()
    
    # Попробуем найти по ID или никнейму
    user = None
    if user_input.isdigit():
        user = await db.get_user(int(user_input))
    elif user_input.startswith("@"):
        user = await db._one(
            "SELECT * FROM users WHERE username = ?",
            (user_input[1:],),
        )
    else:
        user = await db._one(
            "SELECT * FROM users WHERE username = ?",
            (user_input,),
        )
    
    if not user:
        return await message.answer("❌ Участник не найден. Проверь ID или никнейм.")
    
    if user["status"] != "accepted":
        return await message.answer(f"⚠️ Этот участник ещё не в сообществе (статус: {user['status']}).")
    
    # Сохраняем выбранного пользователя в FSM
    await state.update_data(selected_tg_id=user["tg_id"], selected_nick=user.get("nick", "?"))
    await state.set_state(UserMessageState.type_message)
    
    nick = user.get("nick", f"@{user.get('username', '?')}")
    text = (
        f"{ui.header('✉️', f'СООБЩЕНИЕ ДЛЯ {ui.esc(nick)}')}\\n\\n"
        "Отправь текст сообщения. Можно использовать форматирование Telegram."
    )
    await message.answer(text, reply_markup=cancel_kb())


@router.message(UserMessageState.type_message, F.text)
async def message_user_send(message: Message, state: FSMContext):
    """Админ отправляет сообщение."""
    level = await db.get_level(message.from_user.id)
    if level < MIN_LEVEL:
        await state.clear()
        return
    
    data = await state.get_data()
    to_user = data.get("selected_tg_id")
    
    if not to_user:
        await state.clear()
        return
    
    text = message.html_text.strip()
    if len(text) < 5:
        return await message.answer("⚠️ Сообщение слишком короткое.")
    
    msg_id = await db.send_user_message(message.from_user.id, to_user, text)
    
    # Отправить участнику
    prefix = "💬 Сообщение от администрации:\n\n"
    try:
        await message.bot.send_message(to_user, prefix + text)
    except Exception as e:
        await message.answer(f"⚠️ Не удалось отправить сообщение: {e}")
        await state.clear()
        return
    
    await message.answer(
        f"✅ Сообщение отправлено участнику\n"
        f"ID сообщения: {msg_id}"
    )
    await state.clear()
